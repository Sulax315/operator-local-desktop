#!/usr/bin/env python3
"""
Publish financial control-loop questions to Metabase and wire them onto a dashboard.

All financial business logic stays in Postgres views; this script only upserts native
SQL saved questions and dashboard placement via the Metabase REST API.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, MutableMapping, Optional
from urllib.parse import urljoin

import requests


TRANSIENT_STATUS = {429, 502, 503, 504}
GRID_WIDTH = 18

SQL_KPI_LATEST = """SELECT *
FROM v_financial_exec_kpi_latest
WHERE project_code = {{project_code}}
[[AND as_of_cost_report_date = {{as_of_cost_report_date}}]];
"""

SQL_PROFIT_TREND = """SELECT *
FROM v_financial_profit_trend
WHERE project_code = {{project_code}}
ORDER BY profit_month;
"""

SQL_COST_VARIANCE = """SELECT *
FROM v_financial_cost_code_variance_latest
WHERE project_code = {{project_code}}
[[AND as_of_cost_report_date = {{as_of_cost_report_date}}]]
ORDER BY budget_less_committed ASC NULLS LAST, open_commitments DESC NULLS LAST, spent_to_date DESC NULLS LAST
LIMIT 500;
"""

SQL_EXCEPTIONS = """SELECT *
FROM v_financial_exception_alerts_latest
WHERE project_code = {{project_code}}
[[AND as_of_cost_report_date = {{as_of_cost_report_date}}]]
ORDER BY as_of_cost_report_date DESC, budget_less_committed ASC NULLS LAST;
"""

SQL_MITIGATION_PRIORITY = """SELECT *
FROM v_financial_mitigation_priority_latest
WHERE project_code = {{project_code}}
[[AND as_of_cost_report_date = {{as_of_cost_report_date}}]]
ORDER BY mitigation_priority_score DESC NULLS LAST, budget_less_committed ASC NULLS LAST
LIMIT 250;
"""

SQL_CHANGE_ORDER_ROLLUP = """SELECT *
FROM v_financial_cost_rollup_by_change_order_kind_latest
WHERE project_code = {{project_code}}
[[AND as_of_cost_report_date = {{as_of_cost_report_date}}]]
ORDER BY cost_line_kind ASC;
"""

SQL_OPERATOR_HEALTH = """SELECT * FROM v_financial_operator_health;"""

SQL_DATA_QUALITY_FLAGS = """SELECT *
FROM v_financial_data_quality_flags_latest
WHERE project_code = {{project_code}}
ORDER BY as_of_cost_report_date DESC NULLS LAST;"""


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
    # v_financial_profit_trend has no as_of_cost_report_date; omit template tag + dashboard mapping.
    with_as_of: bool = False


QUESTION_SPECS: list[QuestionSpec] = [
    QuestionSpec("kpi_latest", "Financial KPI Latest", SQL_KPI_LATEST, "table", 18, 4, 0, with_as_of=True),
    QuestionSpec(
        "profit_trend",
        "Financial Profit Trend",
        SQL_PROFIT_TREND,
        "line",
        18,
        6,
        1,
        {"graph.dimensions": ["profit_month"], "graph.metrics": ["projected_profit"]},
    ),
    QuestionSpec(
        "cost_variance",
        "Financial Cost Code Variance (Top 500)",
        SQL_COST_VARIANCE,
        "table",
        18,
        8,
        2,
        with_as_of=True,
    ),
    QuestionSpec(
        "mitigation_priority",
        "Financial Mitigation Priority (latest batch)",
        SQL_MITIGATION_PRIORITY,
        "table",
        18,
        8,
        3,
        with_as_of=True,
    ),
    QuestionSpec("exceptions", "Financial Exception Alerts", SQL_EXCEPTIONS, "table", 18, 8, 4, with_as_of=True),
    QuestionSpec(
        "change_order_rollup",
        "Change orders vs standard lines (18=owner CO, 21=CM contingency)",
        SQL_CHANGE_ORDER_ROLLUP,
        "table",
        18,
        5,
        5,
        with_as_of=True,
    ),
    QuestionSpec(
        "operator_health",
        "Financial operator health (views + migration registry)",
        SQL_OPERATOR_HEALTH,
        "table",
        18,
        3,
        6,
    ),
    QuestionSpec(
        "data_quality_flags",
        "Financial data quality flags (latest cost batch)",
        SQL_DATA_QUALITY_FLAGS,
        "table",
        18,
        4,
        7,
    ),
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


def build_native_dataset_query(database_id: int, sql: str, template_tags: dict[str, Any]) -> dict[str, Any]:
    return {
        "lib/type": "mbql/query",
        "database": database_id,
        "stages": [{"lib/type": "mbql.stage/native", "native": sql, "template-tags": template_tags}],
    }


def financial_template_tags(
    default_project_code: str,
    existing: Optional[dict[str, Any]] = None,
    *,
    with_as_of: bool,
) -> dict[str, Any]:
    prev = existing if isinstance(existing, dict) else {}
    prev_pc = prev.get("project_code")
    prev_pc_id = prev_pc.get("id") if isinstance(prev_pc, dict) else None
    tag_pc_id = str(prev_pc_id or uuid.uuid4())
    out: dict[str, Any] = {
        "project_code": {
            "type": "text",
            "name": "project_code",
            "id": tag_pc_id,
            "display-name": "Project code",
            "required": True,
            "default": default_project_code,
        }
    }
    if with_as_of:
        prev_dt = prev.get("as_of_cost_report_date")
        prev_dt_id = prev_dt.get("id") if isinstance(prev_dt, dict) else None
        tag_dt_id = str(prev_dt_id or uuid.uuid4())
        out["as_of_cost_report_date"] = {
            "type": "date",
            "name": "as_of_cost_report_date",
            "id": tag_dt_id,
            "display-name": "As of (cost report date)",
            "required": False,
        }
    return out


def rectangles_overlap(a_row: int, a_col: int, a_sx: int, a_sy: int, b_row: int, b_col: int, b_sx: int, b_sy: int) -> bool:
    return not (a_col + a_sx <= b_col or b_col + b_sx <= a_col or a_row + a_sy <= b_row or b_row + b_sy <= a_row)


def find_top_free_slot(
    occupied: Iterable[dict[str, Any]],
    size_x: int,
    size_y: int,
    max_scan_rows: int = 80,
) -> tuple[int, int]:
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
    dashboard_action: str = ""
    questions: dict[str, dict[str, Any]] = field(default_factory=dict)
    dashcards: dict[str, dict[str, Any]] = field(default_factory=dict)

    def print_report(self) -> None:
        print("\n=== Summary ===")
        print(f"auth_method:        {self.auth_method}")
        print(f"database:           {self.database} (id={self.database_id})")
        print(f"collection:         {self.collection} (id={self.collection_id}) [{self.collection_action}]")
        print(f"dashboard:          {self.dashboard} (id={self.dashboard_id}) [{self.dashboard_action}]")
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
        self.session.headers["User-Agent"] = "bratek-financial-metabase-publish/1.0"

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


def find_dashboard_id_by_name(client: MetabaseClient, name: str) -> Optional[int]:
    for dash in list_dashboards(client):
        if dash.get("name") == name and dash.get("id") is not None:
            return int(dash["id"])
    return None


def create_dashboard(
    client: MetabaseClient,
    *,
    name: str,
    collection_id: Optional[int],
    default_project_code: str,
    default_as_of_cost_report_date: Optional[str] = None,
) -> tuple[int, str]:
    as_of_param: dict[str, Any] = {
        "name": "As of (cost report date)",
        "slug": "as_of_cost_report_date",
        "id": "as_of_cost_report_date",
        "type": "date/single",
        "sectionId": "date",
    }
    if default_as_of_cost_report_date:
        as_of_param["default"] = default_as_of_cost_report_date
    payload: dict[str, Any] = {
        "name": name,
        "description": "Auto-created by scripts/publish_financial_control_loop_metabase.py",
        "parameters": [
            {
                "name": "Project code",
                "slug": "project_code",
                "id": "project_code",
                "type": "string/=",
                "sectionId": "string",
                "default": default_project_code,
            },
            as_of_param,
        ],
        "dashcards": [],
        "tabs": [{"name": "Financial"}],
        "width": "fixed",
    }
    if collection_id is not None:
        payload["collection_id"] = collection_id

    res = client.request("POST", "api/dashboard", json_body=payload, mutates=True)
    if res is None:
        return 0, "would_create"
    return int(res["id"]), "created"


def resolve_or_create_dashboard(
    client: MetabaseClient,
    *,
    dashboard_id_env: Optional[str],
    dashboard_name_env: Optional[str],
    default_dashboard_name: str,
    collection_id: Optional[int],
    default_project_code: str,
    default_as_of_cost_report_date: Optional[str] = None,
) -> tuple[int, str, str]:
    if dashboard_id_env:
        did = int(dashboard_id_env)
        dash = client.request("GET", f"api/dashboard/{did}")
        return did, str(dash.get("name", "")), "resolved_by_id"

    name = (dashboard_name_env or "").strip() or default_dashboard_name
    existing_id = find_dashboard_id_by_name(client, name)
    if existing_id is not None:
        return existing_id, name, "reused_by_name"

    did, action = create_dashboard(
        client,
        name=name,
        collection_id=collection_id,
        default_project_code=default_project_code,
        default_as_of_cost_report_date=default_as_of_cost_report_date,
    )
    if action == "would_create":
        return 0, name, action
    return did, name, "created"


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
    default_project_code: str,
    with_as_of_tag: bool,
    visualization_settings: Optional[dict[str, Any]] = None,
) -> tuple[int, str]:
    matches = cards_named(client, collection_id, name)
    existing_tags: Optional[dict[str, Any]] = None
    if matches and not client.dry_run:
        existing = get_card(client, int(matches[0]["id"]))
        dq_existing = existing.get("dataset_query") or {}
        stages = dq_existing.get("stages") or []
        if stages and isinstance(stages[0], dict):
            maybe = stages[0].get("template-tags")
            if isinstance(maybe, dict):
                existing_tags = maybe
    template_tags = financial_template_tags(
        default_project_code,
        existing_tags,
        with_as_of=with_as_of_tag,
    )
    dq = build_native_dataset_query(database_id, sql_text, template_tags)
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


def ensure_dashboard_financial_parameters(
    client: MetabaseClient,
    *,
    dashboard_id: int,
    default_project_code: str,
    default_as_of_cost_report_date: Optional[str] = None,
) -> None:
    if client.dry_run:
        return

    dash = client.request("GET", f"api/dashboard/{dashboard_id}")
    params = list(dash.get("parameters") or [])
    desired_project = {
        "name": "Project code",
        "slug": "project_code",
        "id": "project_code",
        "type": "string/=",
        "sectionId": "string",
        "default": default_project_code,
    }
    desired_as_of: dict[str, Any] = {
        "name": "As of (cost report date)",
        "slug": "as_of_cost_report_date",
        "id": "as_of_cost_report_date",
        "type": "date/single",
        "sectionId": "date",
    }
    if default_as_of_cost_report_date:
        desired_as_of["default"] = default_as_of_cost_report_date

    changed = False
    idx_pc = next(
        (i for i, p in enumerate(params) if isinstance(p, dict) and p.get("slug") == "project_code"),
        None,
    )
    if idx_pc is None:
        params.append(desired_project)
        changed = True
    else:
        cur = params[idx_pc]
        merged = {**dict(cur), **{k: v for k, v in desired_project.items() if v is not None}}
        if merged != cur:
            params[idx_pc] = merged
            changed = True

    idx_as = next(
        (i for i, p in enumerate(params) if isinstance(p, dict) and p.get("slug") == "as_of_cost_report_date"),
        None,
    )
    if idx_as is None:
        params.append(desired_as_of)
        changed = True
    else:
        cur = params[idx_as]
        merged = {**dict(cur), **{k: v for k, v in desired_as_of.items() if v is not None}}
        if merged != cur:
            params[idx_as] = merged
            changed = True

    if not changed:
        return

    dashcards = dash.get("dashcards") or []
    put_body = {
        "name": dash.get("name"),
        "description": dash.get("description"),
        "collection_id": dash.get("collection_id"),
        "cache_ttl": dash.get("cache_ttl"),
        "parameters": params,
        "tabs": slim_tabs_for_put(dash.get("tabs")),
        "dashcards": [strip_dashcard_for_put(dict(dc)) for dc in dashcards],
        "width": dash.get("width") or "fixed",
    }
    client.request("PUT", f"api/dashboard/{dashboard_id}", json_body=put_body, mutates=True)


def ensure_dashboard_parameter_mappings(
    client: MetabaseClient,
    *,
    dashboard_id: int,
    card_id: int,
    parameter_slug: str,
    field_ref: str,
) -> None:
    dash = client.request("GET", f"api/dashboard/{dashboard_id}")
    params = dash.get("parameters") or []
    target = None
    for p in params:
        if isinstance(p, dict) and p.get("slug") == parameter_slug:
            target = p
            break
    if target is None or target.get("id") is None:
        return

    dashcards = dash.get("dashcards") or []
    updated = False
    for dc in dashcards:
        if int(dc.get("card_id") or 0) != int(card_id):
            continue
        mappings = dc.get("parameter_mappings") or []
        already = any(
            isinstance(m, dict)
            and m.get("parameter_id") == target.get("id")
            and m.get("card_id") == card_id
            for m in mappings
        )
        if already:
            continue
        mappings.append(
            {
                "parameter_id": target.get("id"),
                "card_id": card_id,
                "target": ["dimension", ["template-tag", field_ref]],
            }
        )
        dc["parameter_mappings"] = mappings
        updated = True

    if not updated:
        return

    put_body = {
        "name": dash.get("name"),
        "description": dash.get("description"),
        "collection_id": dash.get("collection_id"),
        "cache_ttl": dash.get("cache_ttl"),
        "parameters": params,
        "tabs": slim_tabs_for_put(dash.get("tabs")),
        "dashcards": [strip_dashcard_for_put(dict(dc)) for dc in dashcards],
        "width": dash.get("width") or "fixed",
    }
    client.request("PUT", f"api/dashboard/{dashboard_id}", json_body=put_body, mutates=True)


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
    parser = argparse.ArgumentParser(description="Publish financial control-loop questions to Metabase.")
    parser.add_argument("--env-file", help="Optional KEY=VALUE env file.")
    parser.add_argument("--dry-run", action="store_true", help="Skip mutating calls.")
    parser.add_argument(
        "--dashboard-name",
        help="Override METABASE_DASHBOARD_NAME. If empty and no METABASE_DASHBOARD_ID, a new dashboard is created.",
    )
    parser.add_argument("--collection-name", help="Override METABASE_COLLECTION_NAME.")
    parser.add_argument(
        "--default-project-code",
        help="Override METABASE_DEFAULT_PROJECT_CODE (native SQL variable default + dashboard filter default).",
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

    db_name = os.environ.get("METABASE_DATABASE_NAME", "").strip()
    coll_name = (args.collection_name or os.environ.get("METABASE_COLLECTION_NAME", "")).strip()
    dash_id_env = os.environ.get("METABASE_DASHBOARD_ID", "").strip()
    dash_name_env = (args.dashboard_name or os.environ.get("METABASE_DASHBOARD_NAME", "")).strip()
    default_dash_name = os.environ.get(
        "METABASE_FINANCIAL_DASHBOARD_DEFAULT_NAME",
        "Project Financial Control Loop - v1",
    ).strip()
    default_project_code = (args.default_project_code or os.environ.get("METABASE_DEFAULT_PROJECT_CODE", "219128")).strip()
    default_as_of_raw = os.environ.get("METABASE_DEFAULT_AS_OF_COST_REPORT_DATE", "").strip()
    default_as_of_cost_report_date = default_as_of_raw or None

    if not db_name:
        print("ERROR: METABASE_DATABASE_NAME is required", file=sys.stderr)
        return 2
    if not coll_name:
        print("ERROR: METABASE_COLLECTION_NAME is required (or pass --collection-name)", file=sys.stderr)
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

    did, dname, daction = resolve_or_create_dashboard(
        client,
        dashboard_id_env=dash_id_env or None,
        dashboard_name_env=dash_name_env or None,
        default_dashboard_name=default_dash_name,
        collection_id=coll_id,
        default_project_code=default_project_code,
        default_as_of_cost_report_date=default_as_of_cost_report_date,
    )
    summary.dashboard_id = did
    summary.dashboard = dname
    summary.dashboard_action = daction
    if did == 0:
        print("Dashboard would be created. Re-run without --dry-run.", file=sys.stderr)
        summary.print_report()
        return 3

    ensure_dashboard_financial_parameters(
        client,
        dashboard_id=did,
        default_project_code=default_project_code,
        default_as_of_cost_report_date=default_as_of_cost_report_date,
    )

    targets: dict[str, dict[str, Any]] = {}
    for spec in QUESTION_SPECS:
        qid, action = upsert_native_card(
            client,
            collection_id=coll_id,
            database_id=db_id,
            name=spec.name,
            sql_text=spec.sql,
            display=spec.display,
            default_project_code=default_project_code,
            with_as_of_tag=spec.with_as_of,
            visualization_settings=spec.visualization_settings,
        )
        summary.questions[spec.key] = {"id": qid, "action": action}
        targets[spec.key] = {"card_id": qid, "size_x": spec.size_x, "size_y": spec.size_y, "order": spec.order}

    ensure_dashboard_wiring(client, did, targets, summary)

    if not args.dry_run:
        for key, meta in targets.items():
            cid = int(meta["card_id"])
            ensure_dashboard_parameter_mappings(
                client,
                dashboard_id=did,
                card_id=cid,
                parameter_slug="project_code",
                field_ref="project_code",
            )
            spec = next(s for s in QUESTION_SPECS if s.key == key)
            if spec.with_as_of:
                ensure_dashboard_parameter_mappings(
                    client,
                    dashboard_id=did,
                    card_id=cid,
                    parameter_slug="as_of_cost_report_date",
                    field_ref="as_of_cost_report_date",
                )

    summary.print_report()
    print(f"\nOpen dashboard: {base.rstrip('/')}/dashboard/{did}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
