"""Ensure required run contract files are enforced by validator."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "scripts" / "operator_run.py"
VALIDATE = REPO_ROOT / "scripts" / "validate_operator_run.py"
REGISTRY = REPO_ROOT / "build_control" / "operator_local" / "09_WORKFLOW_REGISTRY.json"


def _create_compare_run(root: Path) -> Path:
    left = root / "left.md"
    right = root / "right.md"
    left.write_text("A\n", encoding="utf-8")
    right.write_text("B\n", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--runs-root",
            str(root / "runs"),
            "--registry",
            str(REGISTRY),
            "compare",
            str(left),
            str(right),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr + proc.stdout)
    run_id = re.search(r"^Run ID:\s+(\S+)$", proc.stdout, re.MULTILINE)
    if not run_id:
        raise AssertionError(f"missing run id in output:\n{proc.stdout}")
    return root / "runs" / run_id.group(1)


class TestRunContractRequiredFiles(unittest.TestCase):
    def test_validator_fails_when_required_files_missing(self) -> None:
        required = [
            "manifest.json",
            "operator_summary.md",
            "logs/execution_trace.md",
            "outputs/operator_envelope.json",
            "outputs/operator_envelope.md",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for rel in required:
                case_root = base / rel.replace("/", "_")
                case_root.mkdir(parents=True, exist_ok=True)
                run_dir = _create_compare_run(case_root)
                target = run_dir / rel
                target.unlink()
                val = subprocess.run(
                    [
                        sys.executable,
                        str(VALIDATE),
                        "--run-dir",
                        str(run_dir),
                        "--workflow-registry",
                        str(REGISTRY),
                    ],
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(val.returncode, 0, f"validator should fail when missing {rel}")


if __name__ == "__main__":
    unittest.main()
