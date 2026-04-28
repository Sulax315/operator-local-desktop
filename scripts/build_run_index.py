#!/usr/bin/env python3
"""Build run index from Operator Local run manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def collect(runs_root: Path) -> list[dict]:
    rows: list[dict] = []
    if not runs_root.exists():
        return rows
    for run_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        rows.append(
            {
                "run_id": manifest.get("run_id", run_dir.name),
                "timestamp_utc": manifest.get("timestamp_utc", ""),
                "phase": manifest.get("phase", ""),
                "status": manifest.get("status", ""),
                "workflow_name": manifest.get("workflow_name", ""),
                "has_blockers": bool(manifest.get("blockers")),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Create runs/index.json")
    parser.add_argument("--runs-root", default="runs")
    parser.add_argument("--output", default="runs/index.json")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    rows = collect(runs_root)
    output = {"count": len(rows), "runs": rows}

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote run index: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
