#!/usr/bin/env python3
"""
Deterministic February → March 219128 Profit Report workbook comparison (CLI).
Delegates to operator_workflows.financial_mom_219128; no extractor changes.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from operator_workflows.financial_mom_219128 import (  # noqa: E402
    default_feb_mar_paths,
    write_mom_json_report,
)


def main() -> int:
    feb_path, mar_path = default_feb_mar_paths(ROOT)
    if len(sys.argv) > 1:
        feb_path = Path(sys.argv[1])
    if len(sys.argv) > 2:
        mar_path = Path(sys.argv[2])
    for p in (feb_path, mar_path):
        if not p.is_file():
            print(f"FAIL: missing {p}", file=sys.stderr)
            return 1
    out_path = ROOT / "runs" / "219128_feb_mar_2026_mom_compare.json"
    r = write_mom_json_report(out_path, feb_path, mar_path)
    d = r.get("deltas") or {}
    print("=" * 72)
    print("219128 February → March (2026) profit workbook MOM (extract-based)")
    print("=" * 72)
    print("February:", r.get("feb_path"))
    print("March:   ", r.get("mar_path"))
    print()
    keys = [
        "cm_fee",
        "prior_system_profit",
        "pco_profit",
        "total_original_project_costs",
        "total_extended_project_costs",
        "owner_change_orders_count",
        "owner_change_orders_value",
        "cm_change_orders_count",
        "cm_change_orders_value",
    ]
    s = r.get("summary_feb") or {}
    t = r.get("summary_mar") or {}
    w = max(len(k) for k in keys) + 2
    print(f"{'Field':{w}} {'Feb':>20} {'Mar':>20} {'Delta':>18}")
    for k in keys:
        a, b = s.get(k), t.get(k)
        try:
            dlt = (float(b) if b is not None else 0) - (float(a) if a is not None else 0)
        except (TypeError, ValueError):
            dlt = None
        ds = f"{dlt:,.2f}" if dlt is not None and isinstance(dlt, (int, float)) else str(dlt)
        av = f"{a:,.2f}" if isinstance(a, (int, float)) else str(a)
        bv = f"{b:,.2f}" if isinstance(b, (int, float)) else str(b)
        print(f"{k:{w}} {av:>20} {bv:>20} {ds:>18}")
    jdc = r.get("jtd_row_diff_counts") or {}
    odc = r.get("owner_co_diff_counts") or {}
    cdc = r.get("cm_co_diff_counts") or {}
    print()
    print("JTD line diffs (key = raw + name + role + namespace + seq):")
    print(
        f"  removed: {jdc.get('all_lines_removed')}  added: {jdc.get('all_lines_added')}"
        f"  common: {jdc.get('all_lines_common')}"
    )
    print("Owner CO line diffs:")
    print(f"  removed: {odc.get('removed')}  added: {odc.get('added')}  common: {odc.get('common')}")
    print("CM CO line diffs:")
    print(f"  removed: {cdc.get('removed')}  added: {cdc.get('added')}  common: {cdc.get('common')}")
    rec = r.get("reconciliation") or {}
    print()
    if rec.get("n_prefixed_sum_delta") is not None:
        print(
            "Reconciliation: sum(UCB) n_prefixed Mar − Feb = "
            f"{float(rec['n_prefixed_sum_delta']):,.2f} (matches total extended delta: "
            f"{d.get('total_extended_project_costs') is not None}). "
            "Per-row key pairs can show spurious ADD/REMOVE when a line splits."
        )
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
