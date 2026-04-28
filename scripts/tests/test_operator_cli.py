"""Integration tests for scripts/operator_run.py CLI."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "scripts" / "operator_run.py"
REGISTRY = REPO_ROOT / "build_control" / "operator_local" / "09_WORKFLOW_REGISTRY.json"


def _extract_run_id(stdout: str) -> str:
    match = re.search(r"^Run ID:\s+(\S+)$", stdout, re.MULTILINE)
    if not match:
        raise AssertionError(f"Could not find run id in output:\n{stdout}")
    return match.group(1)


class TestOperatorCli(unittest.TestCase):
    def test_compare_command_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left = root / "left.md"
            right = root / "right.md"
            left.write_text("# Weekly\n\nA\n", encoding="utf-8")
            right.write_text("# Weekly\n\nB\n", encoding="utf-8")

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
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertIn("=== OPERATOR RUN ===", proc.stdout)
            self.assertIn("--- SUMMARY ---", proc.stdout)
            self.assertIn("--- WHAT TO REVIEW ---", proc.stdout)
            self.assertIn("--- OUTPUT PATH ---", proc.stdout)
            self.assertIn("Workflow: wf_compare_markdown", proc.stdout)
            self.assertIn("Changed line count:", proc.stdout)
            self.assertIn("Changed heading lines:", proc.stdout)
            self.assertIn("Significance tier:", proc.stdout)
            self.assertIn("Review changed headings/sections first", proc.stdout)

            run_id = _extract_run_id(proc.stdout)
            run_dir = root / "runs" / run_id
            self.assertTrue((run_dir / "outputs" / "operator_envelope.json").exists())
            self.assertTrue((run_dir / "outputs" / "operator_envelope.md").exists())

    def test_risk_command_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "notes.md"
            src.write_text("Risk: vendor outage likely impacts SLA.\n", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--runs-root",
                    str(root / "runs"),
                    "--registry",
                    str(REGISTRY),
                    "risk",
                    str(src),
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertIn("Workflow: wf_extract_risk_lines", proc.stdout)
            self.assertIn("Action-needed items:", proc.stdout)
            self.assertIn("Informational items:", proc.stdout)
            self.assertIn("Truncated output:", proc.stdout)
            self.assertIn("Review action-needed items first", proc.stdout)

    def test_financial_command_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left = root / "prior.md"
            right = root / "curr.md"
            left.write_text("Revenue $100\n", encoding="utf-8")
            right.write_text("Revenue $110\n", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--runs-root",
                    str(root / "runs"),
                    "--registry",
                    str(REGISTRY),
                    "financial",
                    str(left),
                    str(right),
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertIn("Workflow: wf_financial_markdown_delta", proc.stdout)
            self.assertIn("Primary material items:", proc.stdout)
            self.assertIn("Audit-only items:", proc.stdout)
            self.assertIn("High-confidence primary exists:", proc.stdout)
            self.assertIn("Review primary material items first", proc.stdout)

    def test_invalid_input_fails_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--runs-root",
                    str(root / "runs"),
                    "--registry",
                    str(REGISTRY),
                    "compare",
                    str(root / "missing_left.md"),
                    str(root / "missing_right.md"),
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("ERROR:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
