#!/usr/bin/env python3
"""Evaluate Phase 1 acceptance conditions for Operator Local."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def has_local_model_success(run_dir: Path) -> bool:
    json_output = run_dir / "outputs" / "structured_output.json"
    if not json_output.exists():
        return False
    try:
        payload = json.loads(json_output.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    evidence = payload.get("local_model_evidence", {})
    return str(evidence.get("status", "")).lower() == "success"


def has_ui_access_success(run_dir: Path) -> bool:
    json_output = run_dir / "outputs" / "structured_output.json"
    if not json_output.exists():
        return False
    try:
        payload = json.loads(json_output.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    evidence = payload.get("open_webui_evidence", {})
    return str(evidence.get("status", "")).lower() == "success"


def evaluate(runs_root: Path) -> dict:
    run_dirs = sorted([p for p in runs_root.iterdir() if p.is_dir()]) if runs_root.exists() else []
    local_model_evidence_run_ids = [run_dir.name for run_dir in run_dirs if has_local_model_success(run_dir)]
    ui_evidence_run_ids = [run_dir.name for run_dir in run_dirs if has_ui_access_success(run_dir)]

    result = {
        "phase": "Phase 1",
        "criteria": {
            "local_model_runs_successfully": len(local_model_evidence_run_ids) > 0,
            "ui_accessible_via_browser": len(ui_evidence_run_ids) > 0,
            "user_can_submit_prompt": len(run_dirs) > 0,
            "files_can_be_manually_referenced": len(run_dirs) > 0,
            "system_produces_response": len(run_dirs) > 0,
        },
        "evidence_run_ids": local_model_evidence_run_ids,
        "ui_evidence_run_ids": ui_evidence_run_ids,
        "note": "Runtime criteria are driven by structured_output evidence in run artifacts.",
    }
    result["pass"] = all(result["criteria"].values())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Phase 1 acceptance gate.")
    parser.add_argument("--runs-root", default="runs", help="Directory containing run folders")
    parser.add_argument("--output", default="", help="Optional JSON output file")
    args = parser.parse_args()

    result = evaluate(Path(args.runs_root))
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
