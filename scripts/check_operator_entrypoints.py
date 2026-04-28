#!/usr/bin/env python3
"""Validate declared Operator Local entrypoints and wrapper delegation invariants."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_file_contains(path: Path, needle: str) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if needle not in text:
        raise ValueError(f"{path} missing expected substring: {needle!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check operator entrypoint declarations.")
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    spec_path = repo / "scripts" / "operator_entrypoints.json"
    spec = read_json(spec_path)

    for rel in spec.get("phase_3_wrapper_coverage_bar", []):
        p = (repo / str(rel)).resolve()
        if not p.exists():
            raise SystemExit(f"Missing declared coverage path: {p}")

    makefile = repo / "Makefile"
    assert_file_contains(makefile, "scripts/init_operator_run.py")
    assert_file_contains(makefile, "scripts/operator_run.py")
    assert_file_contains(makefile, "scripts/run_workflow.py")
    assert_file_contains(makefile, "scripts/operator_emit_ci_summary.py")

    run_workflow = repo / "scripts" / "run_workflow.py"
    assert_file_contains(run_workflow, "from operator_envelope import")

    operator_cli = repo / "scripts" / "operator_run.py"
    assert_file_contains(operator_cli, "init_operator_run.py")
    assert_file_contains(operator_cli, "run_workflow.py")
    assert_file_contains(operator_cli, "validate_operator_run.py")

    operator_wrapper = repo / "operator"
    assert_file_contains(operator_wrapper, "scripts/operator_run.py")

    emitter = repo / "scripts" / "operator_emit_ci_summary.py"
    assert_file_contains(emitter, "from operator_envelope import")

    snapshot_cycle = repo / "scripts" / "operator_run_snapshot_cycle.py"
    assert_file_contains(snapshot_cycle, "from operator_envelope import")

    financial_cycle = repo / "scripts" / "operator_run_financial_cycle.py"
    assert_file_contains(financial_cycle, "from operator_envelope import")

    weekly_cycle = repo / "scripts" / "operator_run_weekly_cycle.py"
    assert_file_contains(weekly_cycle, "from operator_envelope import")

    print(f"PASS: operator entrypoints OK ({spec_path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
