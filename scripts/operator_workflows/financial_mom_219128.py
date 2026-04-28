"""
Deterministic February → March 219128 profit workbook MOM report.
Reuses the same keying and diff rules as compare_219128_profit_mom.py; no extractor changes.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from operator_workflows.excel_financial_extractor import (
    extract_financial_snapshot_from_workbook,
    infer_project_id_from_workbook_path,
)


def default_feb_mar_paths(repo_root: Path) -> tuple[Path, Path]:
    p = repo_root / "runtime" / "financial_reports" / "219128"
    return (
        p / "219128 Profit Report Update_2026-02-25.xlsx",
        p / "219128 Profit Report Update_2026-03-25.xlsx",
    )


def _norm_name(s: Any) -> str:
    return " ".join(str(s or "").split()).strip()


def _base_key(
    r: dict[str, Any],
) -> tuple[str, str, str, str, str | None]:
    raw = str(r.get("raw_cost_code") or "").strip()
    name = _norm_name(r.get("cost_code_name"))
    role = str(r.get("component_role") or "")
    ns = str(r.get("cost_code_namespace") or "")
    ct = str(r.get("co_type") or "") or None
    return (raw, name, role, ns, ct)


def _index_rows(
    rows: list[dict[str, Any]],
    *,
    co_type_filter: str | None = None,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    filtered = rows
    if co_type_filter is not None:
        filtered = [r for r in rows if str(r.get("co_type") or "") == co_type_filter]

    g: dict[tuple[str, str, str, str, str | None], list[dict[str, Any]]] = defaultdict(list)
    for r in filtered:
        k = _base_key(r)
        g[(k[0], k[1], k[2], k[3], k[4])].append(r)

    out: dict[tuple[Any, ...], dict[str, Any]] = {}
    for k, lst in g.items():
        lst.sort(key=lambda x: (int(x.get("excel_row") or 0),))
        for i, r in enumerate(lst):
            out[(*k, i)] = r
    return out


def _index_jtd_all(jtd_rows: list[dict[str, Any]]) -> dict[tuple[Any, ...], dict[str, Any]]:
    g: dict[tuple[str, str, str, str, None], list[dict[str, Any]]] = defaultdict(list)
    for r in jtd_rows:
        t = (str(r.get("raw_cost_code") or "").strip(), _norm_name(r.get("cost_code_name")))
        t2 = str(r.get("component_role") or "")
        t3 = str(r.get("cost_code_namespace") or "")
        g[(t[0], t[1], t2, t3, None)].append(r)
    out: dict[tuple[Any, ...], dict[str, Any]] = {}
    for k, lst in g.items():
        lst.sort(key=lambda x: (int(x.get("excel_row") or 0),))
        for i, r in enumerate(lst):
            out[(*k, i)] = r
    return out


def _diff_indexed(
    feb: dict[tuple[Any, ...], dict[str, Any]],
    mar: dict[tuple[Any, ...], dict[str, Any]],
) -> dict[str, Any]:
    fkeys, mkeys = set(feb), set(mar)
    return {
        "removed_keys": sorted(fkeys - mkeys, key=str),
        "added_keys": sorted(mkeys - fkeys, key=str),
        "common_keys": sorted(fkeys & mkeys, key=str),
    }


def _ucb(r: dict[str, Any] | None) -> float:
    if not r:
        return 0.0
    v = r.get("update_current_budget")
    return float(v) if v is not None else 0.0


def _row_struct(r: dict[str, Any] | None) -> dict[str, Any]:
    if not r:
        return {
            "raw_cost_code": None,
            "display_cost_code": None,
            "cost_code_name": None,
            "component_role": None,
            "cost_code_namespace": None,
        }
    return {
        "raw_cost_code": r.get("raw_cost_code"),
        "display_cost_code": r.get("display_cost_code") or r.get("cost_code"),
        "cost_code_name": r.get("cost_code_name"),
        "component_role": r.get("component_role"),
        "cost_code_namespace": r.get("cost_code_namespace"),
    }


def _drill(
    section: str,
    change_kind: str,
    rf: dict[str, Any] | None,
    rm: dict[str, Any] | None,
    delta_ucb: float,
) -> dict[str, Any]:
    base = _row_struct(rf or rm)
    return {
        "section": section,
        "change_kind": change_kind,
        **base,
        "update_current_budget_feb": _ucb(rf) if rf is not None else None,
        "update_current_budget_mar": _ucb(rm) if rm is not None else None,
        "delta_ucb": float(delta_ucb),
        "excel_row_feb": int(rf.get("excel_row") or 0) or None if rf else None,
        "excel_row_mar": int(rm.get("excel_row") or 0) or None if rm else None,
    }


def _summarize_wps(wps: dict[str, Any], label: str) -> dict[str, Any]:
    jtd = wps.get("jtd_profit_extraction") or {}
    return {
        "label": label,
        "cm_fee": wps.get("cm_fee") or (jtd.get("cm_fee_source_row") or {}).get("update_current_budget"),
        "prior_system_profit": wps.get("prior_system_profit"),
        "pco_profit": wps.get("pco_profit"),
        "total_original_project_costs": wps.get("total_original_project_costs"),
        "total_extended_project_costs": wps.get("total_extended_project_costs"),
        "owner_change_orders_count": wps.get("owner_change_orders_count"),
        "owner_change_orders_value": wps.get("owner_change_orders_value"),
        "cm_change_orders_count": wps.get("cm_change_orders_count"),
        "cm_change_orders_value": wps.get("cm_change_orders_value"),
    }


def build_219128_feb_mar_mom_report(
    feb_path: Path,
    mar_path: Path,
) -> dict[str, Any]:
    """
    Full deterministic MOM report for UI/JSON, including row drill and explanation vectors.
    Raises FileNotFoundError or ValueError on invalid inputs.
    """
    for p in (feb_path, mar_path):
        if not p.is_file():
            msg = f"workbook not found: {p}"
            raise FileNotFoundError(msg)
    pid_f = infer_project_id_from_workbook_path(feb_path)
    pid_m = infer_project_id_from_workbook_path(mar_path)
    if pid_f != pid_m or pid_f != "219128":
        raise ValueError(f"expected project 219128, got {pid_f!r} vs {pid_m!r}")

    sn_f = extract_financial_snapshot_from_workbook(feb_path)
    sn_m = extract_financial_snapshot_from_workbook(mar_path)
    wps_f = sn_f.get("workbook_profit_summary") or {}
    wps_m = sn_m.get("workbook_profit_summary") or {}
    jf = wps_f.get("jtd_profit_extraction") or {}
    jm = wps_m.get("jtd_profit_extraction") or {}

    rows_f = list(jf.get("jtd_cost_code_rows") or [])
    rows_m = list(jm.get("jtd_cost_code_rows") or [])
    own_f = list(jf.get("owner_change_order_rows") or [])
    own_m = list(jm.get("owner_change_order_rows") or [])
    cm_f = list(jf.get("cm_change_order_rows") or [])
    cm_m = list(jm.get("cm_change_order_rows") or [])

    idx_f = _index_jtd_all(rows_f)
    idx_m = _index_jtd_all(rows_m)
    d_all = _diff_indexed(idx_f, idx_m)

    ext_deltas: list[tuple[dict[str, Any], float]] = []
    for k in d_all["common_keys"]:
        rf, rm = idx_f[k], idx_m[k]
        if str(rf.get("cost_code_namespace")) != "n_prefixed":
            continue
        dv = _ucb(rm) - _ucb(rf)
        if abs(dv) > 0.005 or rf.get("excel_row") != rm.get("excel_row"):
            ext_deltas.append((_drill("extended", "common", rf, rm, dv), dv))
    for k in d_all["added_keys"]:
        r = idx_m[k]
        if str(r.get("cost_code_namespace")) != "n_prefixed":
            continue
        u = _ucb(r)
        if abs(u) > 0.005:
            ext_deltas.append((_drill("extended", "added", None, r, u), u))
    for k in d_all["removed_keys"]:
        r = idx_f[k]
        if str(r.get("cost_code_namespace")) != "n_prefixed":
            continue
        u = _ucb(r)
        if abs(u) > 0.005:
            ext_deltas.append((_drill("extended", "removed", r, None, -u), -u))
    ext_deltas.sort(key=lambda t: abs(t[1]), reverse=True)
    ext_struct = [d for d, _ in ext_deltas]

    o_f = _index_rows(own_f, co_type_filter="Owner")
    o_m = _index_rows(own_m, co_type_filter="Owner")
    d_o = _diff_indexed(o_f, o_m)
    own_vec: list[tuple[dict[str, Any], float]] = []
    for k in d_o["common_keys"]:
        rf, rm = o_f[k], o_m[k]
        dv = _ucb(rm) - _ucb(rf)
        if abs(dv) > 0.005 or rf.get("excel_row") != rm.get("excel_row"):
            own_vec.append((_drill("owner_co", "common", rf, rm, dv), abs(dv)))
    for k in d_o["added_keys"]:
        r = o_m[k]
        u = _ucb(r)
        own_vec.append((_drill("owner_co", "added", None, r, u), abs(u)))
    for k in d_o["removed_keys"]:
        r = o_f[k]
        u = -_ucb(r)
        own_vec.append((_drill("owner_co", "removed", r, None, u), abs(u)))
    own_vec.sort(key=lambda t: t[1], reverse=True)
    own_struct = [d for d, _ in own_vec]

    c_f = _index_rows(cm_f, co_type_filter="CM")
    c_m = _index_rows(cm_m, co_type_filter="CM")
    d_c = _diff_indexed(c_f, c_m)
    cm_vec: list[tuple[dict[str, Any], float]] = []
    for k in d_c["common_keys"]:
        rf, rm = c_f[k], c_m[k]
        dv = _ucb(rm) - _ucb(rf)
        if abs(dv) > 0.005 or rf.get("excel_row") != rm.get("excel_row"):
            cm_vec.append((_drill("cm_co", "common", rf, rm, dv), abs(dv)))
    for k in d_c["added_keys"]:
        r = c_m[k]
        u = _ucb(r)
        cm_vec.append((_drill("cm_co", "added", None, r, u), abs(u)))
    for k in d_c["removed_keys"]:
        r = c_f[k]
        u = -_ucb(r)
        cm_vec.append((_drill("cm_co", "removed", r, None, u), abs(u)))
    cm_vec.sort(key=lambda t: t[1], reverse=True)
    cm_struct = [d for d, _ in cm_vec]

    sum_f_ext = sum(_ucb(r) for r in rows_f if str(r.get("cost_code_namespace") or "") == "n_prefixed")
    sum_m_ext = sum(_ucb(r) for r in rows_m if str(r.get("cost_code_namespace") or "") == "n_prefixed")

    to_f = (wps_m.get("total_extended_project_costs") or 0) - (wps_f.get("total_extended_project_costs") or 0)
    to_ow = (wps_m.get("owner_change_orders_value") or 0) - (wps_f.get("owner_change_orders_value") or 0)
    to_cmv = (wps_m.get("cm_change_orders_value") or 0) - (wps_f.get("cm_change_orders_value") or 0)

    def _f(x: Any) -> float:
        try:
            return float(x) if x is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    c_fee_f, c_fee_m = _f(wps_f.get("cm_fee")), _f(wps_m.get("cm_fee"))
    psp_f, psp_m = _f(wps_f.get("prior_system_profit")), _f(wps_m.get("prior_system_profit"))
    pco_f, pco_m = _f(wps_f.get("pco_profit")), _f(wps_m.get("pco_profit"))
    return {
        "available": True,
        "schema": "mom_219128_feb_mar_v1",
        "project_id": "219128",
        "period_label_feb": "2026-02-25",
        "period_label_mar": "2026-03-25",
        "feb_path": str(feb_path.resolve()),
        "mar_path": str(mar_path.resolve()),
        "summary_feb": _summarize_wps(wps_f, "February"),
        "summary_mar": _summarize_wps(wps_m, "March"),
        "deltas": {
            "cm_fee": c_fee_m - c_fee_f,
            "prior_system_profit": psp_m - psp_f,
            "pco_profit": pco_m - pco_f,
            "total_original_project_costs": (wps_m.get("total_original_project_costs") or 0)
            - (wps_f.get("total_original_project_costs") or 0),
            "total_extended_project_costs": to_f,
            "owner_change_orders_count": (wps_m.get("owner_change_orders_count") or 0)
            - (wps_f.get("owner_change_orders_count") or 0),
            "owner_change_orders_value": to_ow,
            "cm_change_orders_count": (wps_m.get("cm_change_orders_count") or 0)
            - (wps_f.get("cm_change_orders_count") or 0),
            "cm_change_orders_value": to_cmv,
        },
        "jtd_row_diff_counts": {
            "all_lines_removed": len(d_all["removed_keys"]),
            "all_lines_added": len(d_all["added_keys"]),
            "all_lines_common": len(d_all["common_keys"]),
        },
        "owner_co_diff_counts": {
            "removed": len(d_o["removed_keys"]),
            "added": len(d_o["added_keys"]),
            "common": len(d_o["common_keys"]),
        },
        "cm_co_diff_counts": {
            "removed": len(d_c["removed_keys"]),
            "added": len(d_c["added_keys"]),
            "common": len(d_c["common_keys"]),
        },
        "unchanged_headline_components": {
            "cm_fee_unchanged": c_fee_m == c_fee_f,
            "prior_system_profit_unchanged": psp_m == psp_f,
            "pco_profit_unchanged": pco_m == pco_f,
        },
        "reconciliation": {
            "n_prefixed_ucb_sum_feb": sum_f_ext,
            "n_prefixed_ucb_sum_mar": sum_m_ext,
            "n_prefixed_sum_delta": sum_m_ext - sum_f_ext,
            "matches_total_extended_delta": abs((sum_m_ext - sum_f_ext) - to_f) < 0.02,
            "note": (
                "Per-row key pairs for the same code+name can show ADD/REMOVE pairs when a line splits; "
                "n_prefixed UCB sum delta matches total_extended_project_costs."
            ),
        },
        "explanations": {
            "extended_cost_increase": {
                "headline_delta": to_f,
                "reconciliation": sum_m_ext - sum_f_ext,
                "top_driver_rows": ext_struct[:25],
            },
            "owner_co_increase": {
                "headline_value_delta": to_ow,
                "headline_count_delta": (wps_m.get("owner_change_orders_count") or 0)
                - (wps_f.get("owner_change_orders_count") or 0),
                "top_driver_rows": own_struct[:25],
            },
            "cm_co_increase": {
                "headline_value_delta": to_cmv,
                "headline_count_delta": (wps_m.get("cm_change_orders_count") or 0)
                - (wps_f.get("cm_change_orders_count") or 0),
                "top_driver_rows": cm_struct[:25],
            },
        },
        "row_drill": ext_struct + own_struct + cm_struct,
        "top_n_prefixed_ucb_deltas": [
            {**d, "summary_line": f"{d.get('raw_cost_code')} | {d.get('cost_code_name')} | Δ={d.get('delta_ucb')}"}
            for d in ext_struct[:40]
        ],
    }


def write_mom_json_report(
    out_path: Path,
    feb_path: Path,
    mar_path: Path,
) -> dict[str, Any]:
    r = build_219128_feb_mar_mom_report(feb_path, mar_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8")
    return r
