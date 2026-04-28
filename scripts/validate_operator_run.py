#!/usr/bin/env python3
"""Validate Operator Local run folder contract compliance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_TOP_LEVEL = ["manifest.json", "operator_summary.md", "inputs", "outputs", "logs"]
REQUIRED_SUMMARY_SECTIONS = [
    "## What I did",
    "## What I found",
    "## What I created",
    "## What needs review",
    "## Next actions",
]
REQUIRED_TRACE_KEYS = ["inputs", "actions", "outputs", "assumptions"]

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REGISTRY = SCRIPT_DIR.parent / "build_control" / "operator_local" / "09_WORKFLOW_REGISTRY.json"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def parse_semverish(value: str) -> tuple[int, int, int]:
    parts = (value or "").strip().split(".")
    nums: list[int] = []
    for part in parts[:3]:
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits) if digits else 0)
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def contract_version_at_least(manifest: dict, minimum: str) -> bool:
    current = str(manifest.get("contract_version", "0.0.0"))
    return parse_semverish(current) >= parse_semverish(minimum)


def check_registry_snapshot(manifest: dict, failures: list[str]) -> None:
    snap = manifest.get("registry_snapshot")
    if not isinstance(snap, dict):
        failures.append("Missing registry_snapshot on completed run (contract_version >= 1.1.0)")
        return

    snap_path = snap.get("path")
    snap_sha = snap.get("sha256")
    if not snap_path or not snap_sha:
        failures.append("registry_snapshot missing path or sha256")
        return

    path = Path(str(snap_path))
    if not path.exists():
        failures.append(f"registry_snapshot path missing on disk: {path}")
        return

    import hashlib

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != str(snap_sha):
        failures.append(
            "Registry drift detected: registry file content no longer matches manifest.registry_snapshot.sha256 "
            f"(expected {snap_sha}, got {digest})"
        )


def check_path(path: Path, failures: list[str]) -> None:
    for name in REQUIRED_TOP_LEVEL:
        expected = path / name
        if not expected.exists():
            failures.append(f"Missing required artifact: {expected}")


def check_manifest(path: Path, failures: list[str]) -> None:
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        return

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"Invalid JSON in manifest: {exc}")
        return

    for key in ["run_id", "timestamp_utc", "phase", "status", "trace", "artifacts"]:
        if key not in manifest:
            failures.append(f"Manifest missing key: {key}")

    trace = manifest.get("trace", {})
    if not isinstance(trace, dict):
        failures.append("Manifest trace must be an object")
    else:
        for key in REQUIRED_TRACE_KEYS:
            if key not in trace:
                failures.append(f"Manifest trace missing key: {key}")
            elif not isinstance(trace[key], list):
                failures.append(f"Manifest trace key must be list: {key}")


def find_workflow_definition(registry: dict, name: str) -> dict | None:
    for wf in registry.get("workflows", []):
        if wf.get("name") == name:
            return wf
    return None


def check_workflow_registry(run_dir: Path, manifest: dict, registry_path: Path, failures: list[str]) -> None:
    workflow_name = manifest.get("workflow_name")
    if not workflow_name:
        failures.append("Manifest missing workflow_name for registry validation")
        return

    if not registry_path.exists():
        failures.append(f"Workflow registry not found: {registry_path}")
        return

    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"Invalid workflow registry JSON: {exc}")
        return

    wf = find_workflow_definition(registry, str(workflow_name))
    if wf is None:
        failures.append(f"Workflow not registered: {workflow_name}")
        return

    if wf.get("enabled") is False:
        failures.append(f"Workflow disabled in registry: {workflow_name}")

    for rel in wf.get("required_artifacts", []) or []:
        expected = run_dir / rel
        if not expected.exists():
            failures.append(f"Missing workflow-required artifact ({workflow_name}): {expected}")


def check_summary(path: Path, failures: list[str]) -> None:
    summary_path = path / "operator_summary.md"
    if not summary_path.exists():
        return

    summary = summary_path.read_text(encoding="utf-8")
    for section in REQUIRED_SUMMARY_SECTIONS:
        if section not in summary:
            failures.append(f"Summary missing required section: {section}")


def check_trace_log(path: Path, failures: list[str]) -> None:
    trace_path = path / "logs" / "execution_trace.md"
    if not trace_path.exists():
        failures.append(f"Missing trace log: {trace_path}")
        return
    trace = trace_path.read_text(encoding="utf-8")
    for heading in ["## Inputs", "## Actions", "## Outputs", "## Assumptions"]:
        if heading not in trace:
            failures.append(f"Trace log missing heading: {heading}")


def validate_run(run_dir: Path, *, registry_path: Path, enforce_registry: bool) -> tuple[bool, list[str]]:
    failures: list[str] = []
    check_path(run_dir, failures)

    manifest_path = run_dir / "manifest.json"
    manifest: dict = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}

    check_manifest(run_dir, failures)
    check_summary(run_dir, failures)
    check_trace_log(run_dir, failures)

    if enforce_registry:
        if manifest_path.exists() and isinstance(manifest, dict):
            status = str(manifest.get("status", "")).lower()
            if status in {"initialized", "pending"}:
                return len(failures) == 0, failures
            check_workflow_registry(run_dir, manifest, registry_path, failures)
            if status in {"completed", "completed_with_blocker", "failed"} and contract_version_at_least(manifest, "1.1.0"):
                check_registry_snapshot(manifest, failures)
            if status in {"completed", "completed_with_blocker", "failed"} and contract_version_at_least(manifest, "1.2.0"):
                from operator_envelope import validate_envelope_files

                try:
                    validate_envelope_files(run_dir)
                except Exception as exc:  # noqa: BLE001 - aggregate validation errors
                    failures.append(f"Operator envelope validation failed: {exc}")

    return len(failures) == 0, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Operator Local run contract.")
    parser.add_argument("--run-dir", required=True, help="Path to run directory")
    parser.add_argument(
        "--workflow-registry",
        default=str(DEFAULT_REGISTRY),
        help="Path to workflow registry JSON used for optional workflow artifact checks",
    )
    parser.add_argument(
        "--no-workflow-registry",
        action="store_true",
        help="Disable workflow registry artifact enforcement",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    registry_path = Path(args.workflow_registry)
    ok, failures = validate_run(run_dir, registry_path=registry_path, enforce_registry=not args.no_workflow_registry)
    if ok:
        print(f"PASS: {run_dir}")
        return 0

    print(f"FAIL: {run_dir}")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
