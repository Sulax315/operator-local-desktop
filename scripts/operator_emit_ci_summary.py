#!/usr/bin/env python3
"""Emit a durable Operator Local CI summary under runs/ with canonical envelope artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from operator_envelope import build_envelope, write_envelope_artifacts


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_registry_snapshot(repo_root: Path) -> dict:
    registry_path = (repo_root / "build_control" / "operator_local" / "09_WORKFLOW_REGISTRY.json").resolve()
    raw = registry_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8"))
    return {
        "path": str(registry_path),
        "version": str(payload.get("version", "unknown")),
        "sha256": digest,
    }


def emit(*, repo_root: Path, gate_path: Path, health_md_path: Path, force: bool) -> Path:
    run_dir = repo_root / "runs" / "_operator_surface" / "ci_last"
    (run_dir / "inputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)

    gate = read_json(gate_path) if gate_path.exists() else {}
    health_md = health_md_path.read_text(encoding="utf-8") if health_md_path.exists() else ""
    registry_snapshot = read_registry_snapshot(repo_root)

    manifest = {
        "run_id": "ci_last",
        "timestamp_utc": utc_now_iso(),
        "phase": "Phase 3",
        "status": "completed",
        "contract_version": "1.2.0",
        "system_identity": "Operator Local",
        "workflow_name": "ci_operator_surface_summary",
        "operator": "single_user",
        "runner": {"name": "ci_summary_emitter", "version": "1.0.0"},
        "registry_snapshot": registry_snapshot,
        "trace": {
            "inputs": [str(gate_path.resolve()), str(health_md_path.resolve())],
            "actions": [],
            "outputs": [],
            "assumptions": [
                "CI summary is operator-facing output and must be envelope-wrapped with durable artifacts under runs/.",
            ],
        },
        "artifacts": {
            "operator_summary": "operator_summary.md",
            "inputs_dir": "inputs/",
            "outputs_dir": "outputs/",
            "logs_dir": "logs/",
        },
        "review": {"needs_review": False, "review_notes": []},
    }

    summary_md = "\n".join(
        [
            "# Operator Summary — ci_last",
            "",
            "## What I did",
            "- Emitted CI operator surface summary after CI loop artifacts were produced.",
            "",
            "## What I found",
            f"- Phase gate pass: {gate.get('pass')}",
            "",
            "## What I created",
            f"- `{run_dir / 'outputs' / 'ci_summary.json'}`",
            f"- `{run_dir / 'outputs' / 'ci_health_snapshot.md'}`",
            "",
            "## What needs review",
            "- Confirm CI artifacts reflect the intended environment and repo state.",
            "",
            "## Next actions",
            "- If gate failed, fix root causes and re-run CI.",
            "",
        ]
    )

    ci_summary = {
        "generated_utc": manifest["timestamp_utc"],
        "gate": gate,
        "health_report_markdown_chars": len(health_md),
    }

    paths_written: list[str] = []

    def write_if_missing(path: Path, content: str) -> None:
        if path.exists() and not force:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        paths_written.append(str(path.resolve()))

    write_if_missing(run_dir / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    write_if_missing(run_dir / "operator_summary.md", summary_md)
    write_if_missing(run_dir / "outputs" / "ci_summary.json", json.dumps(ci_summary, indent=2) + "\n")
    write_if_missing(run_dir / "outputs" / "ci_health_snapshot.md", health_md)

    created = [
        {"path": str((run_dir / "outputs" / "ci_summary.json").resolve()), "description": "CI summary JSON snapshot"},
        {"path": str((run_dir / "outputs" / "ci_health_snapshot.md").resolve()), "description": "CI health report markdown snapshot"},
    ]

    envelope = build_envelope(
        what_i_did=[
            "Generated CI operator surface summary artifacts under runs/_operator_surface/ci_last/.",
        ],
        what_i_found=[
            f"Gate pass={gate.get('pass')}",
        ],
        what_i_created=created,
        what_needs_review=[
            "Confirm CI outputs are acceptable for the target environment.",
        ],
        next_actions=[
            "If CI failed, remediate and re-run scripts/operator_local_ci.sh.",
        ],
        run={"run_id": "ci_last", "manifest_path": str((run_dir / "manifest.json").resolve())},
    )
    env_paths = write_envelope_artifacts(run_dir, envelope)

    manifest = read_json(run_dir / "manifest.json")
    manifest["trace"]["actions"] = [
        "Read CI gate report",
        "Read CI health markdown",
        "Wrote CI summary JSON + health markdown snapshot",
        "Emitted canonical operator envelope artifacts",
    ]
    manifest["trace"]["outputs"] = [
        str((run_dir / "outputs" / "ci_summary.json").resolve()),
        str((run_dir / "outputs" / "ci_health_snapshot.md").resolve()),
        env_paths["json"],
        env_paths["markdown"],
    ]
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    trace_md = "\n".join(
        [
            "# Execution Trace — ci_last",
            "",
            "## Inputs",
            "\n".join(f"- `{p}`" for p in manifest["trace"]["inputs"]) or "- (none)",
            "",
            "## Actions",
            "\n".join(f"- {a}" for a in manifest["trace"]["actions"]) or "- (none)",
            "",
            "## Outputs",
            "\n".join(f"- `{p}`" for p in manifest["trace"]["outputs"]) or "- (none)",
            "",
            "## Assumptions",
            "\n".join(f"- {a}" for a in manifest["trace"]["assumptions"]) or "- (none)",
            "",
        ]
    ).rstrip() + "\n"
    write_if_missing(run_dir / "logs" / "execution_trace.md", trace_md)

    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit CI operator summary with envelope artifacts.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--gate", default="runs/phase1_gate_report.json")
    parser.add_argument("--health-md", default="runs/operator_local_health_report.md")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    gate_path = (repo_root / args.gate).resolve() if not Path(args.gate).is_absolute() else Path(args.gate).resolve()
    health_path = (repo_root / args.health_md).resolve() if not Path(args.health_md).is_absolute() else Path(args.health_md).resolve()

    run_dir = emit(repo_root=repo_root, gate_path=gate_path, health_md_path=health_path, force=args.force)
    print(f"OK: wrote CI operator surface summary at {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
