"""End-to-end weekly-style workflows: wf_compare_markdown + wf_extract_risk_lines (init → run → validate)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "build_control" / "operator_local" / "09_WORKFLOW_REGISTRY.json"


class TestWfCompareMarkdownIntegration(unittest.TestCase):
    def test_compare_workflow_passes_contract_validation(self) -> None:
        """Test plan: init run → run workflow with two inputs → validate_operator_run (registry + envelope)."""
        run_id = f"tmp_wf_cmp_{uuid.uuid4().hex[:10]}"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            runs = tmp_root / "runs"
            runs.mkdir(parents=True, exist_ok=True)
            left = tmp_root / "left.md"
            right = tmp_root / "right.md"
            left.write_text("# A\n\nLine one.\n", encoding="utf-8")
            right.write_text("# A\n\nLine one.\n\nLine two.\n", encoding="utf-8")

            init = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "init_operator_run.py"),
                    "--run-id",
                    run_id,
                    "--runs-root",
                    str(runs),
                    "--workflow-name",
                    "wf_compare_markdown",
                    "--phase",
                    "Phase 2",
                    "--workflow-registry",
                    str(REGISTRY),
                    "--force",
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(init.returncode, 0, init.stdout + init.stderr)

            run_dir = runs / run_id
            run = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "run_workflow.py"),
                    "--workflow",
                    "wf_compare_markdown",
                    "--run-dir",
                    str(run_dir),
                    "--registry",
                    str(REGISTRY),
                    "--input",
                    str(left),
                    "--input",
                    str(right),
                    "--force",
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

            diff_path = run_dir / "outputs" / "diff.unified.diff"
            self.assertTrue(diff_path.exists(), "registry requires diff.unified.diff")

            val = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "validate_operator_run.py"),
                    "--run-dir",
                    str(run_dir),
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(val.returncode, 0, val.stdout + val.stderr)

            payload = json.loads((run_dir / "outputs" / "structured_output.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("workflow"), "wf_compare_markdown")
            self.assertEqual(payload.get("schema_version"), "1.0")
            self.assertFalse(payload.get("diff_empty"))


class TestWfExtractRiskLinesIntegration(unittest.TestCase):
    def test_extract_workflow_passes_contract_validation(self) -> None:
        """Test plan: init run → single input with risk keyword → validate_operator_run."""
        run_id = f"tmp_wf_risk_{uuid.uuid4().hex[:10]}"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            runs = tmp_root / "runs"
            runs.mkdir(parents=True, exist_ok=True)
            src = tmp_root / "risks.md"
            src.write_text("# Review\n\n- **Risk**: dependency on vendor API.\n", encoding="utf-8")

            init = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "init_operator_run.py"),
                    "--run-id",
                    run_id,
                    "--runs-root",
                    str(runs),
                    "--workflow-name",
                    "wf_extract_risk_lines",
                    "--phase",
                    "Phase 2",
                    "--workflow-registry",
                    str(REGISTRY),
                    "--force",
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(init.returncode, 0, init.stdout + init.stderr)

            run_dir = runs / run_id
            run = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "run_workflow.py"),
                    "--workflow",
                    "wf_extract_risk_lines",
                    "--run-dir",
                    str(run_dir),
                    "--registry",
                    str(REGISTRY),
                    "--input",
                    str(src),
                    "--force",
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

            val = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "validate_operator_run.py"),
                    "--run-dir",
                    str(run_dir),
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(val.returncode, 0, val.stdout + val.stderr)

            payload = json.loads((run_dir / "outputs" / "structured_output.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("workflow"), "wf_extract_risk_lines")
            self.assertEqual(payload.get("schema_version"), "1.0")
            self.assertEqual(payload.get("extraction_rules_id"), "risk_lines_v2")
            self.assertGreaterEqual(int(payload.get("match_count", 0)), 1)


class TestWfFinancialMarkdownDeltaIntegration(unittest.TestCase):
    def test_financial_delta_passes_contract_validation(self) -> None:
        run_id = f"tmp_wf_fin_{uuid.uuid4().hex[:10]}"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            runs = tmp_root / "runs"
            runs.mkdir(parents=True, exist_ok=True)
            prior = tmp_root / "prior_week.md"
            curr = tmp_root / "curr_week.md"
            prior.write_text(
                "# CFO notes\n\nRevenue $100; margin 12%.\n",
                encoding="utf-8",
            )
            curr.write_text(
                "# CFO notes\n\nRevenue $108; margin 11% (YoY pressure).\n",
                encoding="utf-8",
            )

            init = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "init_operator_run.py"),
                    "--run-id",
                    run_id,
                    "--runs-root",
                    str(runs),
                    "--workflow-name",
                    "wf_financial_markdown_delta",
                    "--phase",
                    "Phase 5",
                    "--workflow-registry",
                    str(REGISTRY),
                    "--force",
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(init.returncode, 0, init.stdout + init.stderr)

            run_dir = runs / run_id
            run = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "run_workflow.py"),
                    "--workflow",
                    "wf_financial_markdown_delta",
                    "--run-dir",
                    str(run_dir),
                    "--registry",
                    str(REGISTRY),
                    "--input",
                    str(prior),
                    "--input",
                    str(curr),
                    "--force",
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

            val = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "validate_operator_run.py"),
                    "--run-dir",
                    str(run_dir),
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(val.returncode, 0, val.stdout + val.stderr)

            payload = json.loads((run_dir / "outputs" / "structured_output.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("workflow"), "wf_financial_markdown_delta")
            self.assertEqual(payload.get("schema_version"), "1.0")
            self.assertEqual(payload.get("signal_pattern_id"), "financial_markdown_v3")
            self.assertGreater(int(payload.get("material_diff_line_count", 0)), 0)


if __name__ == "__main__":
    unittest.main()
