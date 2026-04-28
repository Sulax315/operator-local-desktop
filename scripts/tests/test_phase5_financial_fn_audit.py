"""Regression gate for internal false-negative audit on financial workflow."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPhase5FinancialFnAudit(unittest.TestCase):
    def test_financial_fn_audit_manifest(self) -> None:
        script = REPO_ROOT / "scripts" / "run_phase5_financial_fn_audit.py"
        manifest = REPO_ROOT / "build_control" / "operator_local" / "phase5_financial_fn_audit_manifest.json"
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "fn_audit_report.json"
            proc = subprocess.run(
                [sys.executable, str(script), "--manifest", str(manifest), "--output", str(output)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload.get("ok"))

            by_id = {case["id"]: case for case in payload["cases"]}
            # Explicit targeted FN expectations: audit / ignore classes must stay stable.
            self.assertIn("Operating margin compressed YoY", " ".join(by_id["fn_f10_margin_compressed_yoy_no_numbers"]["captured_in_audit"]))
            self.assertEqual(by_id["fn_f11_guidance_cut_slightly_no_numbers"]["captured_in_primary"], [])
            self.assertEqual(by_id["fn_f11_guidance_cut_slightly_no_numbers"]["captured_in_audit"], [])
            self.assertEqual(by_id["fn_f12_revenue_headwinds_no_numbers"]["captured_in_primary"], [])
            self.assertEqual(by_id["fn_f12_revenue_headwinds_no_numbers"]["captured_in_audit"], [])


if __name__ == "__main__":
    unittest.main()
