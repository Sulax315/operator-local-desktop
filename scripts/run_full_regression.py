#!/usr/bin/env python3
"""Single regression gate for Operator Local v1 surfaces."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = REPO_ROOT / "build_control" / "operator_local" / "09_WORKFLOW_REGISTRY.json"
CLI = REPO_ROOT / "scripts" / "operator_run.py"


def _run(command: list[str], *, label: str) -> None:
    proc = subprocess.run(command, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        msg = "\n".join(
            [
                f"[FAIL] {label}",
                " ".join(command),
                "--- stdout ---",
                proc.stdout.rstrip(),
                "--- stderr ---",
                proc.stderr.rstrip(),
            ]
        )
        raise RuntimeError(msg)
    print(f"[PASS] {label}")


def _run_cli_smoke() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        left = root / "a.md"
        right = root / "b.md"
        risk = root / "risk.md"
        fin_a = root / "fin_a.md"
        fin_b = root / "fin_b.md"
        left.write_text("# A\n\none\n", encoding="utf-8")
        right.write_text("# A\n\ntwo\n", encoding="utf-8")
        risk.write_text("Risk: dependency outage may breach SLA.\n", encoding="utf-8")
        fin_a.write_text("Revenue $100M\n", encoding="utf-8")
        fin_b.write_text("Revenue $105M\n", encoding="utf-8")
        runs_root = root / "runs"

        _run(
            [
                sys.executable,
                str(CLI),
                "--runs-root",
                str(runs_root),
                "--registry",
                str(REGISTRY),
                "compare",
                str(left),
                str(right),
            ],
            label="cli smoke compare",
        )
        _run(
            [
                sys.executable,
                str(CLI),
                "--runs-root",
                str(runs_root),
                "--registry",
                str(REGISTRY),
                "risk",
                str(risk),
            ],
            label="cli smoke risk",
        )
        _run(
            [
                sys.executable,
                str(CLI),
                "--runs-root",
                str(runs_root),
                "--registry",
                str(REGISTRY),
                "financial",
                str(fin_a),
                str(fin_b),
            ],
            label="cli smoke financial",
        )


def main() -> int:
    _run([sys.executable, "-m", "unittest", "discover", "-s", "scripts/tests", "-p", "test_*.py"], label="unit tests")
    _run([sys.executable, "scripts/run_phase5_eval_pack.py"], label="phase5 eval pack")
    _run([sys.executable, "scripts/run_phase5_financial_fn_audit.py"], label="financial fn audit")
    _run_cli_smoke()
    print("[PASS] full regression gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
