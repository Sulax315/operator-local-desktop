#!/usr/bin/env python3
"""
Publish week-over-week schedule drift questions to Metabase and wire dashboard tiles.

All schedule business logic stays in Postgres views; this script only upserts native
questions and dashboard placement.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, MutableMapping, Optional
from urllib.parse import urljoin

import requests


TRANSIENT_STATUS = {429, 502, 503, 504}
GRID_WIDTH = 18

SQL_SNAPSHOT_PAIR = """SELECT
  current_snapshot_date,
  prior_snapshot_date
FROM v_schedule_snapshot_pair_latest;
"""

SQL_KPI_STRIP = """SELECT *
FROM v_schedule_wow_kpi_strip;
"""

SQL_KPI_SLIPPED = """SELECT slipped_task_count
FROM v_schedule_wow_kpi_strip;
"""

SQL_KPI_PULLED_IN = """SELECT pulled_in_task_count
FROM v_schedule_wow_kpi_strip;
"""

SQL_KPI_ADDED = """SELECT added_task_count
FROM v_schedule_wow_kpi_strip;
"""

SQL_KPI_REMOVED = """SELECT removed_task_count
FROM v_schedule_wow_kpi_strip;
"""

SQL_KPI_BECAME_CRITICAL = """SELECT became_critical_task_count
FROM v_schedule_wow_kpi_strip;
"""

SQL_KPI_FLOAT_EROSION = """SELECT float_erosion_task_count
FROM v_schedule_wow_kpi_strip;
"""

SQL_SLIP_DISTRIBUTION = """SELECT *
FROM v_schedule_wow_slip_distribution
ORDER BY finish_delta_bucket;
"""

SQL_HEATMAP = """SELECT *
FROM v_schedule_wow_heatmap_phase_control
ORDER BY slipped_task_count DESC, float_erosion_task_count DESC, phase_exec, control_account;
"""

SQL_PHASE_HOTSPOTS = """SELECT
  phase_exec,
  SUM(slipped_task_count)::bigint AS slipped_task_count,
  SUM(float_erosion_task_count)::bigint AS float_erosion_task_count
FROM v_schedule_wow_heatmap_phase_control
GROUP BY phase_exec
ORDER BY slipped_task_count DESC, float_erosion_task_count DESC, phase_exec;
"""

SQL_CRITICAL_TRANSITIONS = """SELECT *
FROM v_schedule_wow_critical_transition_matrix
ORDER BY critical_transition;
"""

SQL_TOP_RISK = """SELECT *
FROM v_schedule_wow_top_risk_tasks
LIMIT 250;
"""

SQL_CHANGE_WATERFALL = """SELECT *
FROM v_schedule_wow_change_class_waterfall
ORDER BY sort_order;
"""

SQL_TIMELINE = """SELECT *
FROM v_schedule_wow_timeline_drilldown
LIMIT 500;
"""


@dataclass
class QuestionSpec:
    key: str
    name: str
    sql: str
    display: str
    size_x: int
    size_y: int
    order: int
    visualization_settings: dict[str, Any] = field(default_factory=dict)


QUESTION_SPECS: list[QuestionSpec] = [
    QuestionSpec("snapshot_pair", "WoW Snapshot Pair", SQL_SNAPSHOT_PAIR, "table", 18, 2, 0),
    QuestionSpec("kpi_strip", "WoW KPI Strip", SQL_KPI_STRIP, "table", 18, 4, 1),
    QuestionSpec("kpi_slipped", "WoW KPI - Slipped Tasks", SQL_KPI_SLIPPED, "scalar", 3, 3, 2),
    QuestionSpec("kpi_pulled_in", "WoW KPI - Pulled-In Tasks", SQL_KPI_PULLED_IN, "scalar", 3, 3, 3),
    QuestionSpec("kpi_added", "WoW KPI - Added Tasks", SQL_KPI_ADDED, "scalar", 3, 3, 4),
    QuestionSpec("kpi_removed", "WoW KPI - Removed Tasks", SQL_KPI_REMOVED, "scalar", 3, 3, 5),
    QuestionSpec(
        "kpi_became_critical",
        "WoW KPI - Became Critical",
        SQL_KPI_BECAME_CRITICAL,
        "scalar",
        3,
        3,
        6,
    ),
    QuestionSpec(
        "kpi_float_erosion",
        "WoW KPI - Float Erosion Tasks",
        SQL_KPI_FLOAT_EROSION,
        "scalar",
        3,
        3,
        7,
    ),
    QuestionSpec(
        "slip_distribution",
        "WoW Slip Distribution",
        SQL_SLIP_DISTRIBUTION,
        "bar",
        9,
        5,
        8,
        {"graph.dimensions": ["finish_delta_bucket"], "graph.metrics": ["task_count"]},
    ),
    QuestionSpec(
        "critical_transition",
        "WoW Critical Transition Matrix",
        SQL_CRITICAL_TRANSITIONS,
        "bar",
        9,
        5,
        9,
        {"graph.dimensions": ["critical_transition"], "graph.metrics": ["task_count"]},
    ),
    QuestionSpec(
        "change_waterfall",
        "WoW Change Class Waterfall",
        SQL_CHANGE_WATERFALL,
        "bar",
        9,
        5,
        10,
        {"graph.dimensions": ["status_change_class"], "graph.metrics": ["task_count"]},
    ),
    QuestionSpec("phase_control_heatmap", "WoW Phase-Control Risk Table", SQL_HEATMAP, "table", 9, 5, 11),
    QuestionSpec(
        "phase_hotspots",
        "WoW Phase Hotspots",
        SQL_PHASE_HOTSPOTS,
        "bar",
        9,
        5,
        12,
        {"graph.dimensions": ["phase_exec"], "graph.metrics": ["slipped_task_count"]},
    ),
    QuestionSpec("top_risk_tasks", "WoW Top Risk Tasks", SQL_TOP_RISK, "table", 18, 8, 13),
    QuestionSpec("timeline_drilldown", "WoW Timeline Drilldown", SQL_TIMELINE, "table", 18, 8, 14),
]


def _truthy(val: Optional[str], default: bool = True) -> bool:
    if val is None or val == "":
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_env_file(path: str) -> None:
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("export "):
                line = line[7:].lstrip()
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def build_native_dataset_query(database_id: int, sql: str) -> dict[str, Any]:
    return {
        "lib/type": "mbql/query",
        "database": database_id,
        "stages": [{"lib/type": "mbql.stage/native", "native": sql}],
    }


@dataclass
class RunSummary:
    auth_method: str = ""
    database: str = ""
    database_id: int = 0
    collection: str = ""
    collection_id: int = 0
    collection_action: str = ""
    dashboard: str = ""
    dashboard_id: int = 0
    questions: dict[str, dict[str, Any]] = field(default_factory=dict)
    dashcards: dict[str, dict[str, Any]] = field(default_factory=dict)

    def print_report(self) -> None:
        print("\n=== Summary ===")
        print(f"auth_method:        {self.auth_method}")
        print(f"database:           {self.database} (id={self.database_id})")
        print(f"collection:         {self.collection} (id={self.collection_id}) [{self.collection_action}]")
        print(f"dashboard:          {self.dashboard} (id={self.dashboard_id})")
        for key, info in self.questions.items():
            print(f"question {key}: id={info.get('id')} action={info.get('action')}")
        for key, info in self.dashcards.items():
            print(f"dashcard {key}: id={info.get('id')} action={info.get('action')} card_id={info.get('card_id')}")


class MetabaseClient:
    def __init__(self, base_url: str, verify_tls: bool, dry_run: bool = False) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.verify_tls = verify_tls
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        self.session.headers["User-Agent"] = "bratek-wow-publisher/1.0"

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    def _backoff(self, attempt: int) -> None:
        base = 0.4 * (2**attempt)
        time.sleep(base + random.random() * 0.25)

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: Optional[Mapping[str, Any]] = None,
        mutates: bool = False,
    ) -> Any:
        if self.dry_run and mutates:
            print(f"[dry-run] would {method} {path}")
            return None

        for attempt in range(4):
            try:
                resp = self.session.request(
                    method,
                    self._url(path),
                    json=json_body,
                    params=params,
                    timeout=120,
                    verify=self.verify_tls,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt == 3:
                    raise RuntimeError(f"{method} {path} failed: {exc}") from exc
                self._backoff(attempt)
                continue
            if resp.status_code in TRANSIENT_STATUS and attempt < 3:
                self._backoff(attempt)
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"{method} {path} -> {resp.status_code}: {resp.text[:2000]}")
            if resp.text == "":
                return None
            return resp.json()
        raise RuntimeError(f"{method} {path} failed after retries")

    def authenticate_api_key(self, api_key: str) -> None:
        self.session.headers["X-Api-Key"] = api_key
        self.request("GET", "api/user/current")

    def authenticate_password(self, username: str, password: str) -> None:
        res = self.request(
            "POST",
            "api/session",
            json_body={"username": username, "password": password},
            mutates=False,
        )
        token = res.get("id")
        if not token:
            raise RuntimeError("Metabase session auth succeeded but token missing")
        self.session.headers["X-Metabase-Session"] = token


def find_database_id(client: MetabaseClient, name: str) -> tuple[int, str]:
    dbs = client.request("GET", "api/database")
    for db in dbs.get("data", []):
        if db.get("name") == name and db.get("id") is not None:
            return int(db["id"]), str(db["name"])
    raise RuntimeError(f'No Metabase database named "{name}" found')


def _flatten_collections(node: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(node, list):
        for item in node:
            out.extend(_flatten_collections(item))
        return out
    if not isinstance(node, dict):
        return out
    if node.get("id") is not None and node.get("name") is not None:
        out.append(node)
    for key in ("children", "collection", "data"):
        child = node.get(key)
        if child is not None:
            out.extend(_flatten_collections(child))
    return out


def list_all_collections(client: MetabaseClient) -> list[dict[str, Any]]:
    raw = client.request("GET", "api/collection/tree")
    flat = _flatten_collections(raw)
    uniq: dict[int, dict[str, Any]] = {}
    for n in flat:
        nid = n.get("id")
        if nid is not None:
            uniq[int(nid)] = n
    return list(uniq.values())


def find_collection_id_by_name(client: MetabaseClient, name: str) -> Optional[int]:
    for node in list_all_collections(client):
        if node.get("name") == name and node.get("id") is not None:
            return int(node["id"])
    return None


def create_collection(client: MetabaseClient, name: str) -> int:
    res = client.request("POST", "api/collection", json_body={"name": name, "parent_id": None}, mutates=True)
    if res is None:
        return 0
    return int(res["id"])


def discover_or_create_collection(client: MetabaseClient, name: str) -> tuple[Optional[int], str]:
    cid = find_collection_id_by_name(client, name)
    if cid is not None:
        return cid, "reused"
    if client.dry_run:
        return None, "would_create"
    return create_collection(client, name), "created"


def list_dashboards(client: MetabaseClient) -> list[dict[str, Any]]:
    return client.request("GET", "api/dashboard", params={"f": "all"})


def resolve_dashboard_id(
    client: MetabaseClient,
    dashboard_id_env: Optional[str],
    dashboard_name: Optional[str],
) -> tuple[int, str]:
    if dashboard_id_env:
        did = int(dashboard_id_env)
        dash = client.request("GET", f"api/dashboard/{did}")
        return did, str(dash.get("name", ""))
    if not dashboard_name:
        raise RuntimeError("Set METABASE_DASHBOARD_ID or METABASE_DASHBOARD_NAME")
    for dash in list_dashboards(client):
        if dash.get("name") == dashboard_name and dash.get("id") is not None:
            return int(dash["id"]), dashboard_name
    raise RuntimeError(f'No dashboard named "{dashboard_name}" found')


def _collection_items(client: MetabaseClient, collection_id: int, models: list[str]) -> list[dict[str, Any]]:
    raw = client.request(
        "GET",
        f"api/collection/{collection_id}/items",
        params={"models": ",".join(models), "archived": "false"},
    )
    if isinstance(raw, dict) and isinstance(raw.get("data"), list):
        return list(raw["data"])
    if isinstance(raw, list):
        return list(raw)
    return []


def cards_named(client: MetabaseClient, collection_id: int, name: str) -> list[dict[str, Any]]:
    items = _collection_items(client, collection_id, ["card"])
    cards = [x for x in items if x.get("model") == "card" and x.get("name") == name]
    return sorted(cards, key=lambda x: int(x["id"]))


def get_card(client: MetabaseClient, card_id: int) -> dict[str, Any]:
    return client.request("GET", f"api/card/{card_id}")


def put_card(client: MetabaseClient, card_id: int, body: dict[str, Any]) -> dict[str, Any]:
    return client.request("PUT", f"api/card/{card_id}", json_body=body, mutates=True)  # type: ignore[arg-type]


def post_card(client: MetabaseClient, body: dict[str, Any]) -> dict[str, Any]:
    return client.request("POST", "api/card", json_body=body, mutates=True)  # type: ignore[arg-type]


def upsert_native_card(
    client: MetabaseClient,
    *,
    collection_id: int,
    database_id: int,
    name: str,
    sql_text: str,
    display: str,
    visualization_settings: Optional[dict[str, Any]] = None,
) -> tuple[int, str]:
    matches = cards_named(client, collection_id, name)
    dq = build_native_dataset_query(database_id, sql_text)
    payload = {
        "name": name,
        "collection_id": collection_id,
        "dataset_query": dq,
        "display": display,
        "visualization_settings": visualization_settings or {},
        "type": "question",
    }
    if not matches:
        res = post_card(client, payload)
        if res is None:
            return 0, "would_create"
        return int(res["id"]), "created"

    keep_id = int(matches[0]["id"])
    if client.dry_run:
        return keep_id, "would_update"

    current = get_card(client, keep_id)
    body = {
        "name": name,
        "collection_id": collection_id,
        "dataset_query": dq,
        "display": display,
        "visualization_settings": visualization_settings
        if visualization_settings is not None
        else (current.get("visualization_settings") or {}),
        "type": current.get("type") or "question",
        "description": current.get("description"),
    }
    put_card(client, keep_id, body)
    for dup in matches[1:]:
        dup_id = int(dup["id"])
        dup_cur = get_card(client, dup_id)
        put_card(
            client,
            dup_id,
            {
                "name": dup_cur.get("name"),
                "archived": True,
                "collection_id": dup_cur.get("collection_id"),
                "dataset_query": dup_cur.get("dataset_query"),
                "display": dup_cur.get("display"),
                "visualization_settings": dup_cur.get("visualization_settings") or {},
                "type": dup_cur.get("type") or "question",
            },
        )
    return keep_id, "updated" if len(matches) == 1 else "updated_deduped"


def rectangles_overlap(a_row: int, a_col: int, a_sx: int, a_sy: int, b_row: int, b_col: int, b_sx: int, b_sy: int) -> bool:
    return not (a_col + a_sx <= b_col or b_col + b_sx <= a_col or a_row + a_sy <= b_row or b_row + b_sy <= a_row)


def find_top_free_slot(occupied: Iterable[dict[str, Any]], size_x: int, size_y: int, max_scan_rows: int = 80) -> tuple[int, int]:
    existing = list(occupied)
    for row in range(0, max_scan_rows):
        for col in range(0, GRID_WIDTH - size_x + 1):
            ok = True
            for e in existing:
                if rectangles_overlap(
                    row,
                    col,
                    size_x,
                    size_y,
                    int(e["row"]),
                    int(e["col"]),
                    int(e["size_x"]),
                    int(e["size_y"]),
                ):
                    ok = False
                    break
            if ok:
                return row, col
    bottom = max((int(e["row"]) + int(e["size_y"])) for e in existing) if existing else 0
    return bottom, 0


def slim_tabs_for_put(tabs: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in tabs or []:
        if isinstance(t, dict) and t.get("id") is not None and t.get("name") is not None:
            out.append({"id": int(t["id"]), "name": str(t["name"])})
    return out


def default_dashboard_tab_id(dash: Mapping[str, Any], stripped: list[dict[str, Any]]) -> int:
    for dc in stripped:
        tid = dc.get("dashboard_tab_id")
        if tid is not None:
            return int(tid)
    tabs = dash.get("tabs") or []
    if tabs and isinstance(tabs[0], dict) and tabs[0].get("id") is not None:
        return int(tabs[0]["id"])
    raise RuntimeError("Dashboard has no tabs; cannot place new dashcards")


def strip_dashcard_for_put(dc: MutableMapping[str, Any]) -> dict[str, Any]:
    keep = {
        "id",
        "card_id",
        "dashboard_id",
        "row",
        "col",
        "size_x",
        "size_y",
        "parameter_mappings",
        "visualization_settings",
        "series",
        "dashboard_tab_id",
    }
    out = {k: dc[k] for k in keep if k in dc and dc[k] is not None}
    out.setdefault("parameter_mappings", [])
    out.setdefault("visualization_settings", {})
    out.setdefault("series", [])
    return out


def ensure_dashboard_wiring(
    client: MetabaseClient,
    dashboard_id: int,
    targets: dict[str, dict[str, Any]],
    summary: RunSummary,
) -> None:
    dash = client.request("GET", f"api/dashboard/{dashboard_id}")
    stripped = [strip_dashcard_for_put(dict(dc)) for dc in (dash.get("dashcards") or [])]
    by_card = {int(dc["card_id"]): dc for dc in stripped if dc.get("card_id") is not None}
    tab_id = default_dashboard_tab_id(dash, stripped)
    next_new_dash_id = -1
    existing_ids = {int(dc["id"]) for dc in stripped if dc.get("id") is not None}
    added_any = False

    for key, meta in sorted(targets.items(), key=lambda kv: kv[1]["order"]):
        cid = int(meta["card_id"])
        if cid in by_card:
            summary.dashcards[key] = {"id": by_card[cid]["id"], "action": "reused", "card_id": cid}
            continue
        if client.dry_run:
            summary.dashcards[key] = {"id": None, "action": "would_add", "card_id": cid}
            added_any = True
            continue

        row, col = find_top_free_slot(stripped, int(meta["size_x"]), int(meta["size_y"]))
        while next_new_dash_id in existing_ids:
            next_new_dash_id -= 1
        new_dc = {
            "id": next_new_dash_id,
            "card_id": cid,
            "row": row,
            "col": col,
            "size_x": int(meta["size_x"]),
            "size_y": int(meta["size_y"]),
            "dashboard_tab_id": tab_id,
            "parameter_mappings": [],
            "visualization_settings": {},
            "series": [],
        }
        stripped.append(new_dc)
        by_card[cid] = new_dc
        existing_ids.add(next_new_dash_id)
        next_new_dash_id -= 1
        summary.dashcards[key] = {"id": None, "action": "added", "card_id": cid}
        added_any = True

    if client.dry_run or not added_any:
        return

    put_body = {
        "name": dash.get("name"),
        "description": dash.get("description"),
        "collection_id": dash.get("collection_id"),
        "cache_ttl": dash.get("cache_ttl"),
        "parameters": dash.get("parameters") or [],
        "tabs": slim_tabs_for_put(dash.get("tabs")),
        "dashcards": stripped,
        "width": dash.get("width") or "fixed",
    }
    client.request("PUT", f"api/dashboard/{dashboard_id}", json_body=put_body, mutates=True)

    refreshed = {
        int(dc["card_id"]): dc
        for dc in (client.request("GET", f"api/dashboard/{dashboard_id}").get("dashcards") or [])
        if dc.get("card_id") is not None
    }
    for key, meta in targets.items():
        cid = int(meta["card_id"])
        if cid in refreshed:
            prev = summary.dashcards.get(key, {})
            summary.dashcards[key] = {"id": refreshed[cid].get("id"), "action": prev.get("action", "reused"), "card_id": cid}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Publish week-over-week schedule drift questions to Metabase.")
    parser.add_argument("--env-file", help="Optional KEY=VALUE env file.")
    parser.add_argument("--dry-run", action="store_true", help="Skip mutating calls.")
    args = parser.parse_args(argv)

    if args.env_file:
        _load_env_file(args.env_file)

    base = os.environ.get("METABASE_BASE_URL", "").strip()
    if not base:
        print("ERROR: METABASE_BASE_URL is required", file=sys.stderr)
        return 2

    verify = _truthy(os.environ.get("METABASE_VERIFY_TLS"), default=True)
    api_key = os.environ.get("METABASE_API_KEY", "").strip()
    user = os.environ.get("METABASE_USERNAME", "").strip()
    pwd = os.environ.get("METABASE_PASSWORD", "").strip()

    db_name = os.environ.get("METABASE_DATABASE_NAME", "").strip()
    coll_name = os.environ.get("METABASE_COLLECTION_NAME", "").strip()
    dash_id_env = os.environ.get("METABASE_DASHBOARD_ID", "").strip()
    dash_name = os.environ.get("METABASE_DASHBOARD_NAME", "").strip()

    if not db_name:
        print("ERROR: METABASE_DATABASE_NAME is required", file=sys.stderr)
        return 2
    if not coll_name:
        print("ERROR: METABASE_COLLECTION_NAME is required", file=sys.stderr)
        return 2

    client = MetabaseClient(base, verify_tls=verify, dry_run=args.dry_run)
    summary = RunSummary()

    if api_key:
        client.authenticate_api_key(api_key)
        summary.auth_method = "METABASE_API_KEY (X-Api-Key)"
    elif user and pwd:
        client.authenticate_password(user, pwd)
        summary.auth_method = "METABASE_USERNAME / METABASE_PASSWORD (session)"
    else:
        print("ERROR: set METABASE_API_KEY or METABASE_USERNAME + METABASE_PASSWORD", file=sys.stderr)
        return 2

    db_id, db_found_name = find_database_id(client, db_name)
    summary.database_id = db_id
    summary.database = db_found_name

    coll_id, coll_action = discover_or_create_collection(client, coll_name)
    summary.collection = coll_name
    summary.collection_id = int(coll_id or 0)
    summary.collection_action = coll_action
    if coll_id is None:
        print("Collection missing and would be created. Re-run without --dry-run.", file=sys.stderr)
        summary.print_report()
        return 3

    did, dname = resolve_dashboard_id(client, dash_id_env or None, dash_name or None)
    summary.dashboard_id = did
    summary.dashboard = dname

    targets: dict[str, dict[str, Any]] = {}
    for spec in QUESTION_SPECS:
        qid, action = upsert_native_card(
            client,
            collection_id=coll_id,
            database_id=db_id,
            name=spec.name,
            sql_text=spec.sql,
            display=spec.display,
            visualization_settings=spec.visualization_settings,
        )
        summary.questions[spec.key] = {"id": qid, "action": action}
        targets[spec.key] = {"card_id": qid, "size_x": spec.size_x, "size_y": spec.size_y, "order": spec.order}

    ensure_dashboard_wiring(client, did, targets, summary)
    summary.print_report()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
