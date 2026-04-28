#!/usr/bin/env python3
"""Initialize Operator Local run folders with contract artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_text(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        return
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: dict, force: bool) -> None:
    if path.exists() and not force:
        return
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def build_manifest(
    run_id: str,
    workflow_name: str,
    phase: str,
    timestamp_utc: str,
    *,
    registry_snapshot: dict | None,
) -> dict:
    manifest: dict = {
        "run_id": run_id,
        "timestamp_utc": timestamp_utc,
        "phase": phase,
        "status": "initialized",
        "contract_version": "1.2.0",
        "system_identity": "Operator Local",
        "workflow_name": workflow_name,
        "operator": "single_user",
        "runner": {"name": "manual", "version": "1.0.0"},
        "trace": {"inputs": [], "actions": [], "outputs": [], "assumptions": []},
        "artifacts": {
            "operator_summary": "operator_summary.md",
            "inputs_dir": "inputs/",
            "outputs_dir": "outputs/",
            "logs_dir": "logs/",
        },
        "review": {
            "needs_review": True,
            "review_notes": [
                "Complete trace arrays during execution.",
                "Mark status completed or completed_with_blocker after review.",
            ],
        },
    }
    if registry_snapshot:
        manifest["registry_snapshot"] = registry_snapshot
    return manifest


def read_registry_snapshot(registry_path: Path) -> dict | None:
    if not registry_path.exists():
        return None

    raw = registry_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        payload = {}

    return {
        "path": str(registry_path.resolve()),
        "version": str(payload.get("version", "unknown")),
        "sha256": digest,
    }


def build_operator_summary(run_id: str) -> str:
    return f"""# Operator Summary — {run_id}

## What I did
- Initialized run scaffold.

## What I found
- Document key findings here.

## What I created
- `manifest.json`
- `inputs/`
- `outputs/`
- `logs/`

## What needs review
- Add reviewer-facing concerns and checks.

## Next actions
- Add immediate next execution steps.
"""


def build_execution_trace(run_id: str) -> str:
    return f"""# Execution Trace — {run_id}

## Inputs
- Add source files and prompt artifacts.

## Actions
- Add each execution step in order.

## Outputs
- Add generated artifact paths and descriptions.

## Assumptions
- Add assumptions made during execution.

## Evidence
- Add command output evidence relevant to acceptance criteria.
"""


def build_prompt_template() -> str:
    return """# Task Prompt

## Prompt
- Describe requested task clearly.

## Input Documents
- Add one or more absolute document paths.
"""


def init_run(
    root: Path,
    run_id: str,
    workflow_name: str,
    phase: str,
    force: bool,
    *,
    registry_snapshot: dict | None,
) -> Path:
    run_dir = root / run_id
    (run_dir / "inputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)

    timestamp_utc = utc_now_iso()
    write_json(
        run_dir / "manifest.json",
        build_manifest(
            run_id,
            workflow_name,
            phase,
            timestamp_utc,
            registry_snapshot=registry_snapshot,
        ),
        force,
    )

    write_text(run_dir / "operator_summary.md", build_operator_summary(run_id), force)
    write_text(run_dir / "logs" / "execution_trace.md", build_execution_trace(run_id), force)
    write_text(run_dir / "inputs" / "task_prompt.md", build_prompt_template(), force)
    write_text(run_dir / "inputs" / ".gitkeep", "\n", force)
    write_text(run_dir / "outputs" / ".gitkeep", "\n", force)
    return run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize Operator Local run contract folder.")
    parser.add_argument("--run-id", required=True, help="Run identifier, for example: test_003")
    parser.add_argument("--runs-root", default="runs", help="Root directory that contains run folders")
    parser.add_argument("--workflow-name", default="manual_task", help="Workflow name for manifest")
    parser.add_argument("--phase", default="Phase 1", help="Current phase label")
    parser.add_argument(
        "--workflow-registry",
        default="build_control/operator_local/09_WORKFLOW_REGISTRY.json",
        help="Path to workflow registry JSON used for snapshot metadata",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing contract files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry_path = Path(args.workflow_registry)
    if not registry_path.is_absolute():
        registry_path = (Path.cwd() / registry_path).resolve()

    run_dir = init_run(
        root=Path(args.runs_root),
        run_id=args.run_id,
        workflow_name=args.workflow_name,
        phase=args.phase,
        force=args.force,
        registry_snapshot=read_registry_snapshot(registry_path),
    )
    print(f"Initialized run scaffold at {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
