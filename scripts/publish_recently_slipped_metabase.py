#!/usr/bin/env python3
"""
VM-local Metabase API publisher: upsert native-SQL questions for Postgres signal views
and wire them onto a target dashboard without duplicate cards on rerun.

Auth and endpoints follow the instance OpenAPI spec served at /api/docs/openapi.json.
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

# ---------------------------------------------------------------------------
# SQL definitions (signal logic remains in Postgres views)
# ---------------------------------------------------------------------------

SQL_RECENTLY_SLIPPED_TASKS = """SELECT
  current_snapshot_date,
  prior_snapshot_date,
  task_id,
  task_name,
  prior_finish_date,
  current_finish_date,
  slip_days
FROM v_signal_recently_slipped_tasks
ORDER BY slip_days DESC, current_finish_date DESC, task_id;
"""

SQL_RECENTLY_SLIPPED_COUNT = """SELECT COUNT(*) AS slipped_task_count
FROM v_signal_recently_slipped_tasks;
"""

SQL_SNAPSHOT_PAIR_HEADER = """SELECT
  prior_snapshot_date,
  current_snapshot_date
FROM v_schedule_snapshot_pair_latest;
"""

NAME_SLIPPED_TABLE = "Recently Slipped Tasks"
NAME_SLIPPED_COUNT = "Recently Slipped Tasks Count"
NAME_SNAPSHOT_HEADER = "Snapshot Pair Header"

# Dashboard may already reference this older card name; adopt it in-place when needed.
LEGACY_SNAPSHOT_CARD_NAMES = frozenset({"v_snapshot_pair"})

GRID_WIDTH = 18
TRANSIENT_STATUS = {429, 502, 503, 504}


def _truthy(val: Optional[str], default: bool = True) -> bool:
    if val is None or val == "":
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_env_file(path: str) -> None:
    """Minimal KEY=VALUE loader (no shell expansion).

    Accepts lines with an optional leading ``export `` (common when operators
    ``source`` the same file in bash). Without stripping, ``export VAR=x``
    would parse as key ``export VAR`` and never set ``VAR``.
    """
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
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def build_native_dataset_query(database_id: int, sql: str) -> dict[str, Any]:
    """MBQL lib shape observed on this Metabase instance (OpenAPI + live cards)."""
    return {
        "lib/type": "mbql/query",
        "database": database_id,
        "stages": [{"lib/type": "mbql.stage/native", "native": sql}],
    }


def rectangles_overlap(
    a_row: int,
    a_col: int,
    a_sx: int,
    a_sy: int,
    b_row: int,
    b_col: int,
    b_sx: int,
    b_sy: int,
) -> bool:
    return not (
        a_col + a_sx <= b_col
        or b_col + b_sx <= a_col
        or a_row + a_sy <= b_row
        or b_row + b_sy <= a_row
    )


def find_top_free_slot(
    occupied: Iterable[dict[str, Any]],
    size_x: int,
    size_y: int,
    max_scan_rows: int = 80,
) -> tuple[int, int]:
    existing = list(occupied)
    for row in range(0, max_scan_rows):
        for col in range(0, GRID_WIDTH - size_x + 1):
            cand = (row, col, size_x, size_y)
            ok = True
            for e in existing:
                if rectangles_overlap(
                    cand[0],
                    cand[1],
                    cand[2],
                    cand[3],
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
    notes: list[str] = field(default_factory=list)

    def print_report(self) -> None:
        print("\n=== Summary ===")
        print(f"auth_method:        {self.auth_method}")
        print(f"database:           {self.database} (id={self.database_id})")
        print(f"collection:         {self.collection} (id={self.collection_id}) [{self.collection_action}]")
        print(f"dashboard:          {self.dashboard} (id={self.dashboard_id})")
        for title, info in self.questions.items():
            print(f"question {title}: id={info.get('id')} action={info.get('action')}")
        for title, info in self.dashcards.items():
            print(f"dashcard {title}: id={info.get('id')} action={info.get('action')} card_id={info.get('card_id')}")


class MetabaseClient:
    def __init__(self, base_url: str, verify_tls: bool, dry_run: bool = False) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.verify_tls = verify_tls
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        self.session.headers["User-Agent"] = "bratek-operator-metabase-publish/1.0"

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

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
            print(f"[dry-run] would {method} {path} body={json.dumps(json_body)[:500]!s}...")
            return None

        last_exc: Optional[Exception] = None
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
                last_exc = exc
                self._backoff(attempt)
                continue
            if resp.status_code in TRANSIENT_STATUS:
                self._backoff(attempt)
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"{method} {path} -> {resp.status_code}: {resp.text[:2000]}")
            if resp.text == "":
                return None
            return resp.json()
        raise RuntimeError(f"{method} {path} failed after retries: {last_exc!r}")

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(min(8.0, 0.4 * (2**attempt)) + random.random() * 0.2)

    def authenticate_api_key(self, api_key: str) -> None:
        self.session.headers["X-Api-Key"] = api_key

    def authenticate_password(self, username: str, password: str) -> None:
        data = self.request("POST", "api/session", json_body={"username": username, "password": password})
        token = data.get("id") if isinstance(data, dict) else None
        if not token:
            raise RuntimeError(f"Unexpected session response: {data!r}")
        self.session.headers["X-Metabase-Session"] = token


def _collection_items(
    client: MetabaseClient,
    collection_id: int,
    models: list[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    offset = 0
    page_size = 200
    while True:
        chunk = client.request(
            "GET",
            f"api/collection/{collection_id}/items",
            params={"models": models, "limit": page_size, "offset": offset},
        )
        data = chunk.get("data", []) if isinstance(chunk, dict) else []
        out.extend(data)
        if not chunk.get("has_more"):
            break
        offset += page_size
    return out


def find_database_id(client: MetabaseClient, name: str) -> tuple[int, str]:
    # Metabase expects a JSON boolean for `saved`; pass lowercase string so the query is not "False".
    rows = client.request("GET", "api/database", params={"saved": "false"})
    for row in rows.get("data", []):
        if row.get("name") == name and row.get("id") is not None:
            return int(row["id"]), str(row["name"])
    raise RuntimeError(f'No database named "{name}" found in Metabase')


def _flatten_collections(obj: Any) -> list[dict[str, Any]]:
    """Normalize /api/collection tree responses into a flat list of collection maps."""
    out: list[dict[str, Any]] = []

    def walk(x: Any) -> None:
        if x is None:
            return
        if isinstance(x, list):
            for item in x:
                walk(item)
            return
        if not isinstance(x, dict):
            return
        if x.get("id") is not None and x.get("name") is not None:
            out.append(x)
        for ch in x.get("children") or []:
            walk(ch)

    walk(obj)
    return out


def list_all_collections(
    client: MetabaseClient,
    archived: bool = False,
) -> list[dict[str, Any]]:
    raw = client.request(
        "GET",
        "api/collection",
        params={
            "archived": archived,
            "exclude-other-user-collections": False,
            "personal-only": False,
        },
    )
    if isinstance(raw, list):
        return _flatten_collections(raw)
    if isinstance(raw, dict):
        if isinstance(raw.get("data"), list):
            return _flatten_collections(raw["data"])
        return _flatten_collections(raw)
    return []


def find_collection_id_by_name(
    client: MetabaseClient,
    name: str,
) -> Optional[int]:
    for node in list_all_collections(client):
        if node.get("name") == name and node.get("id") is not None:
            return int(node["id"])
    return None


def create_collection(client: MetabaseClient, name: str) -> int:
    body = {"name": name, "parent_id": None}
    res = client.request("POST", "api/collection", json_body=body, mutates=True)
    if res is None:
        return 0
    return int(res["id"])


def discover_or_create_collection(
    client: MetabaseClient,
    name: str,
) -> tuple[Optional[int], str]:
    cid = find_collection_id_by_name(client, name)
    if cid is not None:
        return cid, "reused"
    if client.dry_run:
        return None, "would_create"
    new_id = create_collection(client, name)
    return new_id, "created"


def list_dashboards(client: MetabaseClient) -> list[dict[str, Any]]:
    return client.request("GET", "api/dashboard", params={"f": "all"})


def resolve_dashboard_id(
    client: MetabaseClient,
    dashboard_id_env: Optional[str],
    dashboard_name: Optional[str],
) -> tuple[int, str]:
    if dashboard_id_env:
        did = int(dashboard_id_env)
        d = client.request("GET", f"api/dashboard/{did}")
        return did, str(d.get("name", ""))
    if not dashboard_name:
        raise RuntimeError("Set METABASE_DASHBOARD_ID or METABASE_DASHBOARD_NAME")
    for d in list_dashboards(client):
        if d.get("name") == dashboard_name and d.get("id") is not None:
            return int(d["id"]), dashboard_name
    raise RuntimeError(f'No dashboard named "{dashboard_name}" found')


def cards_named(
    client: MetabaseClient,
    collection_id: int,
    name: str,
) -> list[dict[str, Any]]:
    items = _collection_items(client, collection_id, ["card"])
    return sorted(
        [x for x in items if x.get("model") == "card" and x.get("name") == name],
        key=lambda x: int(x["id"]),
    )


def cards_named_any(
    client: MetabaseClient,
    collection_id: int,
    names: set[str],
) -> list[dict[str, Any]]:
    items = _collection_items(client, collection_id, ["card"])
    return sorted(
        [x for x in items if x.get("model") == "card" and x.get("name") in names],
        key=lambda x: int(x["id"]),
    )


def get_card(client: MetabaseClient, card_id: int) -> dict[str, Any]:
    return client.request("GET", f"api/card/{card_id}")


def put_card(
    client: MetabaseClient,
    card_id: int,
    body: dict[str, Any],
) -> dict[str, Any]:
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
) -> tuple[int, str]:
    matches = cards_named(client, collection_id, name)
    dq = build_native_dataset_query(database_id, sql_text)
    payload_base: dict[str, Any] = {
        "name": name,
        "collection_id": collection_id,
        "dataset_query": dq,
        "display": display,
        "visualization_settings": {},
        "type": "question",
    }
    if matches:
        cid = int(matches[0]["id"])
        if client.dry_run:
            return cid, "would_update"
        current = get_card(client, cid)
        body = {
            "name": name,
            "collection_id": collection_id,
            "dataset_query": dq,
            "display": display,
            "visualization_settings": current.get("visualization_settings") or {},
            "type": current.get("type") or "question",
            "description": current.get("description"),
        }
        put_card(client, cid, body)
        return cid, "updated"
    res = post_card(client, payload_base)
    if client.dry_run or res is None:
        return 0, "would_create"
    return int(res["id"]), "created"


def dedupe_cards(
    client: MetabaseClient,
    duplicate_ids: list[int],
) -> None:
    for dup in duplicate_ids:
        if client.dry_run:
            print(f"[dry-run] would archive duplicate card id={dup}")
            continue
        current = get_card(client, dup)
        body = {
            "name": current.get("name"),
            "archived": True,
            "collection_id": current.get("collection_id"),
            "dataset_query": current.get("dataset_query"),
            "display": current.get("display"),
            "visualization_settings": current.get("visualization_settings") or {},
            "type": current.get("type") or "question",
        }
        put_card(client, dup, body)


def resolve_snapshot_header_card(
    client: MetabaseClient,
    collection_id: int,
    database_id: int,
) -> tuple[int, str]:
    primary = cards_named(client, collection_id, NAME_SNAPSHOT_HEADER)
    if primary:
        cid = int(primary[0]["id"])
        dq = build_native_dataset_query(database_id, SQL_SNAPSHOT_PAIR_HEADER)
        if client.dry_run:
            return cid, "would_update"
        cur = get_card(client, cid)
        put_card(
            client,
            cid,
            {
                "name": NAME_SNAPSHOT_HEADER,
                "collection_id": collection_id,
                "dataset_query": dq,
                "display": "table",
                "visualization_settings": cur.get("visualization_settings") or {},
                "type": cur.get("type") or "question",
            },
        )
        return cid, "updated"
    legacy = cards_named_any(client, collection_id, LEGACY_SNAPSHOT_CARD_NAMES)
    if legacy:
        cid = int(legacy[0]["id"])
        dq = build_native_dataset_query(database_id, SQL_SNAPSHOT_PAIR_HEADER)
        if client.dry_run:
            return cid, "would_rename_update"
        cur = get_card(client, cid)
        put_card(
            client,
            cid,
            {
                "name": NAME_SNAPSHOT_HEADER,
                "collection_id": collection_id,
                "dataset_query": dq,
                "display": "table",
                "visualization_settings": cur.get("visualization_settings") or {},
                "type": cur.get("type") or "question",
            },
        )
        return cid, "renamed_from_legacy"
    return upsert_native_card(
        client,
        collection_id=collection_id,
        database_id=database_id,
        name=NAME_SNAPSHOT_HEADER,
        sql_text=SQL_SNAPSHOT_PAIR_HEADER,
        display="table",
    )


def resolve_slipped_table_card(
    client: MetabaseClient,
    collection_id: int,
    database_id: int,
    dashboard_id: int,
    summary: RunSummary,
) -> tuple[int, str]:
    matches = cards_named(client, collection_id, NAME_SLIPPED_TABLE)
    if not matches:
        return upsert_native_card(
            client,
            collection_id=collection_id,
            database_id=database_id,
            name=NAME_SLIPPED_TABLE,
            sql_text=SQL_RECENTLY_SLIPPED_TASKS,
            display="table",
        )
    keep_id = int(matches[0]["id"])
    dup_ids = [int(m["id"]) for m in matches[1:]]
    dq = build_native_dataset_query(database_id, SQL_RECENTLY_SLIPPED_TASKS)
    if client.dry_run:
        if dup_ids:
            summary.notes.append(
                f"[dry-run] would dedupe Recently Slipped Tasks keeping id={keep_id}, archive={dup_ids}"
            )
        return keep_id, "would_update"
    rewire_slipped_cards_on_dashboard(client, dashboard_id, keep_id)
    cur = get_card(client, keep_id)
    put_card(
        client,
        keep_id,
        {
            "name": NAME_SLIPPED_TABLE,
            "collection_id": collection_id,
            "dataset_query": dq,
            "display": "table",
            "visualization_settings": cur.get("visualization_settings") or {},
            "type": cur.get("type") or "question",
        },
    )
    dedupe_cards(client, dup_ids)
    return keep_id, "updated" if not dup_ids else "updated_deduped"


def slim_tabs_for_put(tabs: Any) -> list[dict[str, Any]]:
    """PUT /api/dashboard/{id} accepts only id+name per tab (see instance openapi.json)."""
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
    if "parameter_mappings" not in out:
        out["parameter_mappings"] = []
    if "visualization_settings" not in out:
        out["visualization_settings"] = {}
    if "series" not in out:
        out["series"] = []
    return out


def ensure_dashboard_wiring(
    client: MetabaseClient,
    dashboard_id: int,
    targets: dict[str, dict[str, Any]],
    summary: RunSummary,
) -> None:
    """
    targets: logical_key -> {card_id, size_x, size_y, order}
    order: 0 header, 1 count, 2 table (vertical stack preferred near top)
    """
    dash = client.request("GET", f"api/dashboard/{dashboard_id}")
    dashcards: list[dict[str, Any]] = list(dash.get("dashcards") or [])
    stripped = [strip_dashcard_for_put(dict(dc)) for dc in dashcards]

    # Map existing dashcards by card_id
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
        existing_ids.add(next_new_dash_id)
        next_new_dash_id -= 1
        stripped.append(new_dc)
        by_card[cid] = new_dc
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
    # Refresh ids for newly added dashcards
    dash2 = client.request("GET", f"api/dashboard/{dashboard_id}")
    refreshed = {int(dc["card_id"]): dc for dc in dash2.get("dashcards") or [] if dc.get("card_id")}
    for key, meta in targets.items():
        cid = int(meta["card_id"])
        if cid in refreshed:
            prev = summary.dashcards.get(key, {})
            summary.dashcards[key] = {
                "id": refreshed[cid].get("id"),
                "action": prev.get("action", "reused"),
                "card_id": cid,
            }


def rewire_slipped_cards_on_dashboard(
    client: MetabaseClient,
    dashboard_id: int,
    canonical_card_id: int,
) -> None:
    """Point any dashboard tile whose backing card is named like the slip table at canonical id."""
    if client.dry_run:
        return
    dash = client.request("GET", f"api/dashboard/{dashboard_id}")
    stripped = [strip_dashcard_for_put(dict(dc)) for dc in dash.get("dashcards") or []]
    changed = False
    for dc in stripped:
        cid = dc.get("card_id")
        if cid is None:
            continue
        if int(cid) == canonical_card_id:
            continue
        card = get_card(client, int(cid))
        if card.get("name") == NAME_SLIPPED_TABLE:
            dc["card_id"] = canonical_card_id
            changed = True
    if not changed:
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


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Publish slipped-task signal questions to Metabase.")
    parser.add_argument(
        "--env-file",
        help="Optional path to KEY=VALUE env file (loaded before reading os.environ).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip mutating calls; print intended actions (still requires auth for reads unless no DB work).",
    )
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

    db_name = os.environ.get("METABASE_DATABASE_NAME", "").strip()
    if not db_name:
        print("ERROR: METABASE_DATABASE_NAME is required", file=sys.stderr)
        return 2

    coll_name = os.environ.get("METABASE_COLLECTION_NAME", "").strip()
    if not coll_name:
        print("ERROR: METABASE_COLLECTION_NAME is required", file=sys.stderr)
        return 2

    dash_id_env = os.environ.get("METABASE_DASHBOARD_ID", "").strip()
    dash_name = os.environ.get("METABASE_DASHBOARD_NAME", "").strip()

    db_id, db_found_name = find_database_id(client, db_name)
    summary.database = db_found_name
    summary.database_id = db_id

    coll_id, coll_action = discover_or_create_collection(client, coll_name)
    summary.collection = coll_name
    summary.collection_id = int(coll_id or 0)
    summary.collection_action = coll_action
    if coll_id is None:
        print(
            "Collection is missing and would be created; re-run without --dry-run after review.",
            file=sys.stderr,
        )
        summary.print_report()
        return 3

    did, dname = resolve_dashboard_id(client, dash_id_env or None, dash_name or None)
    summary.dashboard_id = did
    summary.dashboard = dname

    # --- Questions ---
    slip_id, slip_action = resolve_slipped_table_card(
        client, coll_id, db_id, did, summary=summary
    )
    summary.questions[NAME_SLIPPED_TABLE] = {"id": slip_id, "action": slip_action}

    count_id, count_action = upsert_native_card(
        client,
        collection_id=coll_id,
        database_id=db_id,
        name=NAME_SLIPPED_COUNT,
        sql_text=SQL_RECENTLY_SLIPPED_COUNT,
        display="scalar",
    )
    summary.questions[NAME_SLIPPED_COUNT] = {"id": count_id, "action": count_action}

    snap_id, snap_action = resolve_snapshot_header_card(client, coll_id, db_id)
    summary.questions[NAME_SNAPSHOT_HEADER] = {"id": snap_id, "action": snap_action}

    targets = {
        "snapshot_header": {"card_id": snap_id, "size_x": 18, "size_y": 2, "order": 0},
        "slipped_count": {"card_id": count_id, "size_x": 6, "size_y": 3, "order": 1},
        "slipped_table": {"card_id": slip_id, "size_x": 18, "size_y": 8, "order": 2},
    }
    ensure_dashboard_wiring(client, did, targets, summary=summary)

    summary.print_report()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
