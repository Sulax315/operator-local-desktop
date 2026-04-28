#!/usr/bin/env python3
"""Generate a markdown health report for Operator Local runtime artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Operator Local markdown health report.")
    parser.add_argument("--index", default="runs/index.json")
    parser.add_argument("--gate", default="runs/phase1_gate_report.json")
    parser.add_argument("--output", default="runs/operator_local_health_report.md")
    args = parser.parse_args()

    index = load_json(Path(args.index))
    gate = load_json(Path(args.gate))

    runs = index.get("runs", [])
    pass_state = bool(gate.get("pass"))
    criteria = gate.get("criteria", {})

    lines = [
        "# Operator Local Health Report",
        "",
        f"- Total runs indexed: {index.get('count', 0)}",
        f"- Phase gate pass: {pass_state}",
        "",
        "## Gate Criteria",
    ]
    for key, value in criteria.items():
        lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("## Recent Runs")
    for run in runs:
        lines.append(
            "- "
            + f"{run.get('run_id')} | status={run.get('status')} | "
            + f"workflow={run.get('workflow_name')} | blockers={run.get('has_blockers')}"
        )

    lines.append("")
    lines.append("## Required Remediation")
    lines.append("- Capture successful local model runtime evidence in a run output artifact.")
    lines.append("- Capture browser UI accessibility evidence and tie it to a run trace.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote health report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
