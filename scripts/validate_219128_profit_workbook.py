#!/usr/bin/env python3
"""
Live validation: print JTD / CO / profit source mapping for 219128 Profit Report workbooks.
Usage: python3 scripts/validate_219128_profit_workbook.py [path.xlsx]
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from operator_workflows.excel_financial_extractor import (  # noqa: E402
    extract_financial_snapshot_from_workbook,
    infer_project_id_from_workbook_path,
)


def _main() -> int:
    default = ROOT / "runtime" / "financial_reports" / "219128" / "219128 Profit Report Update_2026-02-25.xlsx"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    if not path.is_file():
        print(f"SKIP: workbook not found: {path}", file=sys.stderr)
        return 0
    pid = infer_project_id_from_workbook_path(path)
    print("path:", path)
    print("inferred project_id:", pid)
    snap = extract_financial_snapshot_from_workbook(path)
    wps = snap.get("workbook_profit_summary") or {}
    jtd = wps.get("jtd_profit_extraction") or {}
    o_cnt = wps.get("owner_change_orders_count")
    o_val = wps.get("owner_change_orders_value")
    c_cnt = wps.get("cm_change_orders_count")
    c_val = wps.get("cm_change_orders_value")
    print("owner_change_orders_count:", o_cnt)
    print("owner_change_orders_value:", o_val)
    o_rows = wps.get("owner_change_order_rows") or jtd.get("owner_change_order_rows") or []
    for i, r in enumerate((o_rows or [])[:10]):
        print(
            f"  owner CO[{i}]: {r.get('display_cost_code') or r.get('cost_code')} | "
            f"{r.get('cost_code_name')!s} | UCB={r.get('update_current_budget')} | row={r.get('excel_row')}"
        )
    print("cm_change_orders_count:", c_cnt)
    print("cm_change_orders_value:", c_val)
    c_rows = wps.get("cm_change_order_rows") or jtd.get("cm_change_order_rows") or []
    for i, r in enumerate((c_rows or [])[:10]):
        print(
            f"  CM CO[{i}]: {r.get('display_cost_code') or r.get('cost_code')} | "
            f"{r.get('cost_code_name')!s} | UCB={r.get('update_current_budget')} | row={r.get('excel_row')}"
        )
    print("total_original_project_costs:", wps.get("total_original_project_costs"))
    print("total_extended_project_costs:", wps.get("total_extended_project_costs"))
    cmf = jtd.get("cm_fee_source_row")
    print("CM Fee source row:", cmf)
    if isinstance(cmf, dict):
        print("  CM Fee row component_role:", cmf.get("component_role"), "namespace:", cmf.get("cost_code_namespace"))
    psp = jtd.get("prior_system_profit_jtd_source_row")
    print("prior_system_profit (summary):", wps.get("prior_system_profit"))
    print("Prior-system JTD source row:", psp)
    if isinstance(psp, dict):
        print("  Prior-system row component_role:", psp.get("component_role"), "namespace:", psp.get("cost_code_namespace"))
    p40 = jtd.get("pco_profit_source_row")
    print("PCO Profit source row:", p40)
    for w in jtd.get("jtd_profit_label_warnings") or []:
        print("label warning:", w)
    plim = wps.get("projected_profit_limitations") or []
    if plim:
        print("projected_profit_limitations:")
        for x in plim:
            print("  -", x)
    else:
        print("projected_profit_limitations: (none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
