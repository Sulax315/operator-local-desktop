#!/usr/bin/env python3
"""Run Phase 5 evaluation corpus (handlers) and check phase5_eval_manifest.json expectations."""

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


def _check_expect(case_id: str, workflow: str, so: dict, expect: dict) -> list[str]:
    errs: list[str] = []
    if "diff_empty" in expect:
        if bool(so.get("diff_empty")) != bool(expect["diff_empty"]):
            errs.append(f"{case_id}: diff_empty want {expect['diff_empty']} got {so.get('diff_empty')}")
    if "min_hunk_changes" in expect:
        got = int(so.get("diff_hunk_change_line_count", -1))
        if got < int(expect["min_hunk_changes"]):
            errs.append(f"{case_id}: diff_hunk_change_line_count min {expect['min_hunk_changes']} got {got}")
    if "max_hunk_changes" in expect:
        got = int(so.get("diff_hunk_change_line_count", 999))
        if got > int(expect["max_hunk_changes"]):
            errs.append(f"{case_id}: diff_hunk_change_line_count max {expect['max_hunk_changes']} got {got}")
    if "max_unified_diff_chars" in expect:
        got = int(so.get("unified_diff_chars", 999999))
        if got > int(expect["max_unified_diff_chars"]):
            errs.append(f"{case_id}: unified_diff_chars max {expect['max_unified_diff_chars']} got {got}")
    if workflow == "wf_extract_risk_lines":
        mc = int(so.get("match_count", -1))
        if "min_matches" in expect and mc < int(expect["min_matches"]):
            errs.append(f"{case_id}: match_count min {expect['min_matches']} got {mc}")
        if "max_matches" in expect and mc > int(expect["max_matches"]):
            errs.append(f"{case_id}: match_count max {expect['max_matches']} got {mc}")
        if "must_contain_substr" in expect:
            needle = str(expect["must_contain_substr"])
            texts = [m.get("text", "") for m in so.get("matches", [])]
            if not any(needle in t for t in texts):
                errs.append(f"{case_id}: no match contains {needle!r}")
    if workflow == "wf_financial_markdown_delta":
        ml = int(so.get("material_diff_line_count", -1))
        al = int(so.get("material_diff_audit_line_count", -1))
        if "min_material_lines" in expect and ml < int(expect["min_material_lines"]):
            errs.append(f"{case_id}: material_diff_line_count min {expect['min_material_lines']} got {ml}")
        if "max_material_lines" in expect and ml > int(expect["max_material_lines"]):
            errs.append(f"{case_id}: material_diff_line_count max {expect['max_material_lines']} got {ml}")
        if "must_material_substr" in expect:
            needle = str(expect["must_material_substr"])
            lines = so.get("material_diff_lines") or []
            if not any(needle in ln for ln in lines):
                errs.append(f"{case_id}: no material line contains {needle!r}")
        if "min_audit_lines" in expect and al < int(expect["min_audit_lines"]):
            errs.append(f"{case_id}: material_diff_audit_line_count min {expect['min_audit_lines']} got {al}")
        if "max_audit_lines" in expect and al > int(expect["max_audit_lines"]):
            errs.append(f"{case_id}: material_diff_audit_line_count max {expect['max_audit_lines']} got {al}")
        if "must_audit_substr" in expect:
            needle = str(expect["must_audit_substr"])
            lines = so.get("material_diff_audit_lines") or []
            if not any(needle in ln for ln in lines):
                errs.append(f"{case_id}: no audit line contains {needle!r}")
    return errs


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--manifest",
        type=Path,
        default=REPO_ROOT / "build_control" / "operator_local" / "phase5_eval_manifest.json",
    )
    p.add_argument("--json-summary", action="store_true", help="Emit machine-readable summary to stdout")
    args = p.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    corpus_root = args.manifest.parent / manifest.get("corpus_root", "phase5_eval_corpus")

    all_errs: list[str] = []
    summary: list[dict] = []

    for case in manifest.get("cases", []):
        cid = case["id"]
        wf = case["workflow"]
        paths = [corpus_root / rel for rel in case["inputs"]]
        missing = [p for p in paths if not p.is_file()]
        if missing:
            for path in missing:
                all_errs.append(f"{cid}: missing corpus file {path}")
            continue

        ctx = WorkflowContext(run_dir=corpus_root, inputs=paths)
        out = run_named_workflow(wf, ctx)
        so = out["structured_output"]
        row: dict = {"id": cid, "workflow": wf, "structured_output": so}
        expect = case.get("expect") or {}
        errs = _check_expect(cid, wf, so, expect)
        all_errs.extend(errs)
        row["expect_errors"] = errs
        summary.append(row)

    if args.json_summary:
        print(json.dumps({"ok": not all_errs, "errors": all_errs, "cases": summary}, indent=2))

    if all_errs:
        for e in all_errs:
            print(e, file=sys.stderr)
        return 1

    if not args.json_summary:
        print("phase5_eval_pack: all cases passed", len(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
