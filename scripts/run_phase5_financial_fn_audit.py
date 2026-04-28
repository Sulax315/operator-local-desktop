#!/usr/bin/env python3
"""Internal false-negative audit for wf_financial_markdown_delta."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from operator_workflows.handlers import WorkflowContext, run_named_workflow


def _contains_any(lines: list[str], needle: str) -> bool:
    return any(needle in ln for ln in lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPO_ROOT / "build_control" / "operator_local" / "phase5_financial_fn_audit_manifest.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "build_control" / "operator_local" / "phase5_financial_fn_audit_report.json",
    )
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    corpus_root = args.manifest.parent / manifest["corpus_root"]
    workflow = manifest["workflow"]

    case_reports: list[dict] = []
    errors: list[str] = []
    pattern_buckets = {"primary": [], "audit": [], "ignore": []}

    for case in manifest["cases"]:
        case_id = case["id"]
        inputs = [corpus_root / rel for rel in case["inputs"]]
        ctx = WorkflowContext(run_dir=corpus_root, inputs=inputs)
        payload = run_named_workflow(workflow, ctx)["structured_output"]
        primary = payload.get("material_diff_lines", [])
        audit = payload.get("material_diff_audit_lines", [])

        expected = case.get("expected_material_lines", [])
        expected_render = [f"{row['contains']} => {row['expected_destination']}" for row in expected]
        captured_in_primary: list[str] = []
        captured_in_audit: list[str] = []
        missed: list[str] = []

        for row in expected:
            needle = row["contains"]
            expected_dest = row["expected_destination"]
            in_primary = _contains_any(primary, needle)
            in_audit = _contains_any(audit, needle)

            if in_primary:
                captured_in_primary.append(needle)
            if in_audit:
                captured_in_audit.append(needle)

            if expected_dest == "primary":
                if not in_primary:
                    missed.append(needle)
                    errors.append(f"{case_id}: expected primary missing '{needle}'")
            elif expected_dest == "audit":
                if not in_audit:
                    missed.append(needle)
                    errors.append(f"{case_id}: expected audit missing '{needle}'")
                if in_primary:
                    errors.append(f"{case_id}: expected audit but captured in primary '{needle}'")
            elif expected_dest == "ignore":
                if in_primary or in_audit:
                    errors.append(f"{case_id}: expected ignore but captured '{needle}'")
            else:
                errors.append(f"{case_id}: unknown expected_destination '{expected_dest}'")

            if expected_dest in pattern_buckets:
                pattern_buckets[expected_dest].append(
                    {
                        "case_id": case_id,
                        "needle": needle,
                        "captured_primary": in_primary,
                        "captured_audit": in_audit,
                    }
                )

        case_reports.append(
            {
                "id": case_id,
                "inputs": [str(p) for p in inputs],
                "expected_material_lines": expected_render,
                "captured_in_primary": captured_in_primary,
                "captured_in_audit": captured_in_audit,
                "missed": missed,
                "primary_output_count": len(primary),
                "audit_output_count": len(audit),
            }
        )

    summary = {
        "ok": not errors,
        "workflow": workflow,
        "manifest": str(args.manifest),
        "case_count": len(case_reports),
        "errors": errors,
        "cases": case_reports,
        "pattern_classification": pattern_buckets,
    }
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
