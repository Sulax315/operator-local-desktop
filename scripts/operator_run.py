#!/usr/bin/env python3
"""Operator CLI: one-command workflow execution via init -> run -> validate."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_REGISTRY = REPO_ROOT / "build_control" / "operator_local" / "09_WORKFLOW_REGISTRY.json"
DEFAULT_RUNS_ROOT = REPO_ROOT / "runs"

WORKFLOW_BY_COMMAND = {
    "compare": "wf_compare_markdown",
    "risk": "wf_extract_risk_lines",
    "financial": "wf_financial_markdown_delta",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_phase(registry_path: Path, workflow_name: str) -> str:
    registry = _load_json(registry_path)
    for wf in registry.get("workflows", []):
        if wf.get("name") == workflow_name:
            return str(wf.get("phase", "Phase 5"))
    raise RuntimeError(f"Workflow not found in registry: {workflow_name}")


def _build_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"run_{ts}_{uuid.uuid4().hex[:6]}"


def _run_checked(command: list[str]) -> None:
    proc = subprocess.run(command, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        detail = "\n".join(
            [
                f"Command failed ({proc.returncode}): {' '.join(command)}",
                "--- stdout ---",
                proc.stdout.rstrip(),
                "--- stderr ---",
                proc.stderr.rstrip(),
            ]
        )
        raise RuntimeError(detail)


def _load_envelope(run_dir: Path) -> dict:
    envelope = run_dir / "outputs" / "operator_envelope.json"
    if not envelope.exists():
        raise RuntimeError(f"Missing envelope after run: {envelope}")
    return _load_json(envelope)


def _print_operator_output(*, workflow: str, run_id: str, run_dir: Path, envelope: dict) -> None:
    summary = envelope.get("what_i_found", [])
    review = envelope.get("what_needs_review", [])
    print("=== OPERATOR RUN ===")
    print(f"Workflow: {workflow}")
    print(f"Run ID: {run_id}")
    print("")
    print("--- SUMMARY ---")
    if summary:
        for line in summary:
            print(f"- {line}")
    else:
        print("- (none)")
    print("")
    print("--- WHAT TO REVIEW ---")
    if review:
        for line in review:
            print(f"- {line}")
    else:
        print("- (none)")
    print("")
    print("--- OUTPUT PATH ---")
    print(str((run_dir / "outputs").resolve()))


def _run_operator_command(*, workflow: str, inputs: list[str], runs_root: Path, registry_path: Path) -> int:
    run_id = _build_run_id()
    phase = _resolve_phase(registry_path, workflow)
    run_dir = runs_root / run_id

    _run_checked(
        [
            sys.executable,
            str(SCRIPT_DIR / "init_operator_run.py"),
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
            "--workflow-name",
            workflow,
            "--phase",
            phase,
            "--workflow-registry",
            str(registry_path),
            "--force",
        ]
    )

    run_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "run_workflow.py"),
        "--workflow",
        workflow,
        "--run-dir",
        str(run_dir),
        "--registry",
        str(registry_path),
        "--force",
    ]
    for item in inputs:
        run_cmd.extend(["--input", item])
    _run_checked(run_cmd)

    _run_checked(
        [
            sys.executable,
            str(SCRIPT_DIR / "validate_operator_run.py"),
            "--run-dir",
            str(run_dir),
            "--workflow-registry",
            str(registry_path),
        ]
    )

    envelope = _load_envelope(run_dir)
    _print_operator_output(workflow=workflow, run_id=run_id, run_dir=run_dir, envelope=envelope)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Operator Local CLI")
    parser.add_argument(
        "--runs-root",
        default=str(DEFAULT_RUNS_ROOT),
        help="Root directory for run artifacts (default: runs/)",
    )
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="Workflow registry path",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    compare = sub.add_parser("compare", help="Run deterministic compare workflow")
    compare.add_argument("left")
    compare.add_argument("right")

    risk = sub.add_parser("risk", help="Run deterministic risk extraction workflow")
    risk.add_argument("source")

    financial = sub.add_parser("financial", help="Run deterministic financial delta workflow")
    financial.add_argument("left")
    financial.add_argument("right")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runs_root = Path(args.runs_root).resolve()
    registry_path = Path(args.registry).resolve()
    runs_root.mkdir(parents=True, exist_ok=True)
    if not registry_path.exists():
        print(f"ERROR: registry not found: {registry_path}", file=sys.stderr)
        return 2

    try:
        workflow = WORKFLOW_BY_COMMAND[args.command]
        if args.command == "compare":
            inputs = [str(Path(args.left).resolve()), str(Path(args.right).resolve())]
        elif args.command == "risk":
            inputs = [str(Path(args.source).resolve())]
        else:
            inputs = [str(Path(args.left).resolve()), str(Path(args.right).resolve())]
        return _run_operator_command(
            workflow=workflow,
            inputs=inputs,
            runs_root=runs_root,
            registry_path=registry_path,
        )
    except Exception as exc:  # noqa: BLE001 - top-level CLI boundary
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
