#!/usr/bin/env python3
"""Execute a named Operator Local workflow deterministically and finalize run artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from operator_envelope import build_envelope, write_envelope_artifacts
from operator_workflows.handlers import WorkflowContext, run_named_workflow


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_registry(path: Path) -> dict:
    return load_json(path)


def read_registry_snapshot(registry_path: Path) -> dict:
    raw = registry_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8"))
    return {
        "path": str(registry_path.resolve()),
        "version": str(payload.get("version", "unknown")),
        "sha256": digest,
    }


def find_workflow(registry: dict, name: str) -> dict | None:
    for wf in registry.get("workflows", []):
        if wf.get("name") == name:
            return wf
    return None


def set_trace(
    manifest: dict,
    *,
    inputs: list[str],
    actions: list[str],
    outputs: list[str],
    assumptions: list[str],
) -> None:
    manifest["trace"] = {
        "inputs": list(inputs),
        "actions": list(actions),
        "outputs": list(outputs),
        "assumptions": list(assumptions),
    }


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _fmt_money(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.0f}"


def _workflow_operator_summary(workflow: str, structured: dict) -> tuple[list[str], list[str], list[str]]:
    """Deterministic workflow-specific summary + review guidance for envelope/CLI surfaces."""
    if workflow == "wf_compare_markdown":
        changed = int(structured.get("diff_hunk_change_line_count", 0))
        heading_changed = int(structured.get("diff_heading_lines_changed", 0))
        tier = str(structured.get("diff_significance_tier", "unknown")).upper()
        found = [
            f"Changed line count: {changed}",
            f"Changed heading lines: {heading_changed}",
            f"Significance tier: {tier}",
        ]
        review = [
            "Review changed headings/sections first to confirm structural impact.",
            "Confirm significance tier matches actual operational importance of the edits.",
        ]
        next_actions = ["If significance is medium/large, prioritize review of changed sections in structured_report.md."]
        return found, review, next_actions

    if workflow == "wf_extract_risk_lines":
        matches = structured.get("matches", [])
        actionable = sum(1 for m in matches if str(m.get("triage", "")).lower() == "action_needed")
        match_count = int(structured.get("match_count", 0))
        informational = max(match_count - actionable, 0)
        truncated = bool(structured.get("truncated", False))
        found = [
            f"Action-needed items: {actionable}",
            f"Informational items: {informational}",
            f"Truncated output: {'YES' if truncated else 'NO'}",
        ]
        review = [
            "Review action-needed items first for immediate mitigation/escalation decisions.",
            "Scan informational items only when context is sensitive or deadlines are near.",
        ]
        next_actions = ["If truncated is YES, inspect full source and adjust extraction thresholds before relying on completeness."]
        return found, review, next_actions

    if workflow == "wf_financial_markdown_delta":
        primary = int(structured.get("material_diff_line_count", 0))
        audit = int(structured.get("material_diff_audit_line_count", 0))
        items = structured.get("material_diff_items", [])
        has_high = any(str(it.get("tier", "")).lower() == "high" for it in items)
        found = []
        summary_deltas = structured.get("summary_deltas", {})
        if isinstance(summary_deltas, dict) and isinstance(summary_deltas.get("profit"), (int, float)):
            found.append(f"Profit change: {_fmt_money(float(summary_deltas['profit']))}")
        found.extend(
            [
                f"Primary material items: {primary}",
                f"Audit-only items: {audit}",
                f"High-confidence primary exists: {'YES' if has_high else 'NO'}",
            ]
        )
        top_drivers = [str(x) for x in structured.get("material_diff_lines", [])[:3]]
        for idx, driver in enumerate(top_drivers, start=1):
            found.append(f"Top driver {idx}: {driver}")
        review = [
            "Review primary material items first; treat these as claim-level changes.",
            "Use audit-only items for completeness checks, not as primary decision signal.",
        ]
        next_actions = ["If primary is empty but audit is non-empty, verify whether under-reporting bias is acceptable for this run."]
        return found, review, next_actions

    return (
        ["Workflow completed successfully with deterministic outputs on disk."],
        ["Confirm output semantics meet operational expectations for this workflow."],
        ["If outputs are acceptable, mark review complete in manifest review notes."],
    )


def render_operator_summary(
    *,
    run_id: str,
    workflow: str,
    status: str,
    notes: list[str],
    review_notes: list[str] | None = None,
    next_actions: list[str] | None = None,
) -> str:
    notes_block = "\n".join(f"- {n}" for n in notes) if notes else "- None"
    review_block = (
        "\n".join(f"- {n}" for n in review_notes)
        if review_notes
        else "- Confirm extracted content quality meets operational expectations for this workflow."
    )
    next_actions_block = (
        "\n".join(f"- {n}" for n in next_actions)
        if next_actions
        else "- Promote successful workflow patterns into Phase 2 automation tests."
    )
    return f"""# Operator Summary — {run_id}

## What I did
- Executed deterministic workflow runner for `{workflow}`.

## What I found
{notes_block}

## What I created
- `outputs/structured_report.md`
- `outputs/structured_output.json`
- `outputs/runner.json`
- Updated `manifest.json` and `logs/execution_trace.md`

## What needs review
{review_block}

## Next actions
{next_actions_block}
"""


def render_execution_trace(*, inputs: list[str], actions: list[str], outputs: list[str], assumptions: list[str]) -> str:
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {i}" for i in items) if items else "- (none)"

    return f"""# Execution Trace

## Inputs
{bullets(inputs)}

## Actions
{bullets(actions)}

## Outputs
{bullets(outputs)}

## Assumptions
{bullets(assumptions)}

## Evidence
- See `outputs/runner.json` for structured runner metadata.
"""


def ensure_required_outputs(run_dir: Path, required_artifacts: list[str]) -> None:
    missing = []
    for rel in required_artifacts:
        if not (run_dir / rel).exists():
            missing.append(rel)
    if missing:
        raise RuntimeError(f"Missing required artifacts after run: {missing}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a named Operator Local workflow.")
    parser.add_argument("--workflow", required=True, help="Workflow name from workflow registry JSON")
    parser.add_argument(
        "--registry",
        default="build_control/operator_local/09_WORKFLOW_REGISTRY.json",
        help="Path to workflow registry JSON",
    )
    parser.add_argument("--run-dir", required=True, help="Path to run directory (e.g. runs/test_005)")
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Input file path (repeatable). Order matters for compare workflows.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite outputs if they already exist")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    registry_path = Path(args.registry).resolve()

    if not run_dir.exists():
        print(f"ERROR: run dir does not exist: {run_dir}", file=sys.stderr)
        return 2

    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: missing manifest.json in {run_dir}", file=sys.stderr)
        return 2

    registry = load_registry(registry_path)
    wf_def = find_workflow(registry, args.workflow)
    if wf_def is None:
        print(f"ERROR: workflow not found in registry: {args.workflow}", file=sys.stderr)
        return 2
    if wf_def.get("enabled") is False:
        print(f"ERROR: workflow disabled in registry: {args.workflow}", file=sys.stderr)
        return 2

    manifest = load_json(manifest_path)
    start_ts = utc_now_iso()
    registry_snapshot = read_registry_snapshot(registry_path)
    manifest["registry_snapshot"] = registry_snapshot

    inputs = [Path(p).resolve() for p in args.input]
    for p in inputs:
        if not p.exists():
            print(f"ERROR: input file does not exist: {p}", file=sys.stderr)
            return 2

    actions: list[str] = [
        f"Loaded registry: {registry_path}",
        f"Loaded manifest: {manifest_path}",
        f"Resolved workflow: {args.workflow}",
        f"Resolved inputs: {[str(p) for p in inputs]}",
    ]

    ctx = WorkflowContext(run_dir=run_dir, inputs=inputs)

    outputs_to_write: dict[str, str] = {}
    try:
        result = run_named_workflow(args.workflow, ctx)
        structured = result["structured_output"]
        outputs_to_write["outputs/structured_output.json"] = json.dumps(structured, indent=2) + "\n"
        outputs_to_write["outputs/structured_report.md"] = result["structured_report_md"]
        for rel, content in result.get("extra_outputs", {}).items():
            outputs_to_write[rel] = content

        for rel, content in outputs_to_write.items():
            out_path = run_dir / rel
            if out_path.exists() and not args.force:
                raise RuntimeError(f"Refusing to overwrite without --force: {out_path}")

        for rel, content in outputs_to_write.items():
            out_path = run_dir / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            write_text(out_path, content)

        manifest["workflow_name"] = args.workflow
        manifest["status"] = "completed"
        manifest["contract_version"] = "1.2.0"
        manifest.setdefault("runner", {})
        manifest["runner"] = {"name": "python_deterministic", "version": "1.0.0"}

        runner_meta = {
            "contract_version": "1.2.0",
            "workflow": args.workflow,
            "run_dir": str(run_dir),
            "started_utc": start_ts,
            "finished_utc": utc_now_iso(),
            "status": "success",
            "inputs": [str(p) for p in inputs],
            "registry_snapshot": registry_snapshot,
        }
        write_text(run_dir / "outputs" / "runner.json", json.dumps(runner_meta, indent=2) + "\n")

        created_items: list[dict[str, str]] = []
        for rel in sorted(outputs_to_write.keys()):
            created_items.append(
                {
                    "path": str((run_dir / rel).resolve()),
                    "description": f"Workflow output ({rel})",
                }
            )
        created_items.append(
            {
                "path": str((run_dir / "outputs" / "runner.json").resolve()),
                "description": "Runner metadata (runner.json)",
            }
        )
        found_summary, review_guidance, next_actions = _workflow_operator_summary(args.workflow, structured)

        envelope_paths = write_envelope_artifacts(
            run_dir,
            build_envelope(
                what_i_did=[
                    f"Executed workflow `{args.workflow}` via deterministic runner.",
                    "Wrote structured outputs and validated registry-required artifacts.",
                ],
                what_i_found=found_summary,
                what_i_created=created_items,
                what_needs_review=review_guidance,
                next_actions=next_actions
                + [
                    "If outputs are acceptable, mark review complete in manifest review notes.",
                    "If not, set manifest status to failed and document remediation in execution trace.",
                ],
                run={
                    "run_id": str(manifest.get("run_id", run_dir.name)),
                    "manifest_path": str((run_dir / "manifest.json").resolve()),
                },
            ),
        )

        output_paths = [str((run_dir / rel).resolve()) for rel in outputs_to_write.keys()]
        output_paths.append(str((run_dir / "outputs" / "runner.json").resolve()))
        output_paths.extend([envelope_paths["json"], envelope_paths["markdown"]])
        set_trace(
            manifest,
            inputs=[str(p) for p in inputs],
            actions=actions
            + [
                "Executed deterministic workflow handler",
                "Wrote structured outputs",
                "Validated required artifacts from workflow registry",
            ],
            outputs=output_paths,
            assumptions=[
                "Deterministic workflows do not invoke local models unless explicitly added later.",
            ],
        )

        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        trace_md = render_execution_trace(
            inputs=[str(p) for p in inputs],
            actions=actions
            + [
                "Executed deterministic workflow handler",
                "Wrote structured outputs",
                "Validated required artifacts from workflow registry",
            ],
            outputs=output_paths,
            assumptions=[
                "Deterministic workflows do not invoke local models unless explicitly added later.",
            ],
        )
        write_text(run_dir / "logs" / "execution_trace.md", trace_md)

        summary = render_operator_summary(
            run_id=manifest.get("run_id", run_dir.name),
            workflow=args.workflow,
            status="completed",
            notes=found_summary + [f"Registry definition version: {registry.get('version', 'unknown')}"],
            review_notes=review_guidance,
            next_actions=next_actions,
        )
        write_text(run_dir / "operator_summary.md", summary)

        prompt = "\n".join(
            [
                "# Task Prompt",
                "",
                "## Workflow",
                f"- {args.workflow}",
                "",
                "## Inputs",
                *[f"- `{p}`" for p in inputs],
                "",
            ]
        )
        write_text(run_dir / "inputs" / "task_prompt.md", prompt)

        required = list(wf_def.get("required_artifacts", []))
        ensure_required_outputs(run_dir, required)

        print(f"OK: completed workflow {args.workflow} in {run_dir}")
        return 0
    except Exception as exc:  # noqa: BLE001 - top-level runner boundary
        err = {
            "contract_version": "1.2.0",
            "workflow": args.workflow,
            "run_dir": str(run_dir),
            "started_utc": start_ts,
            "finished_utc": utc_now_iso(),
            "status": "failed",
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "registry_snapshot": registry_snapshot,
        }
        write_text(run_dir / "outputs" / "runner.json", json.dumps(err, indent=2) + "\n")

        manifest["status"] = "failed"
        manifest["contract_version"] = "1.2.0"

        fail_envelope = build_envelope(
            what_i_did=actions + ["Workflow execution failed"],
            what_i_found=[str(exc)],
            what_i_created=[
                {
                    "path": str((run_dir / "outputs" / "runner.json").resolve()),
                    "description": "Failure metadata (runner.json)",
                }
            ],
            what_needs_review=[
                "Review error message and traceback in runner.json.",
                "Decide whether to retry with corrected inputs or workflow parameters.",
            ],
            next_actions=[
                "Fix underlying error and re-run workflow with --force as appropriate.",
            ],
            run={
                "run_id": str(manifest.get("run_id", run_dir.name)),
                "manifest_path": str((run_dir / "manifest.json").resolve()),
            },
        )
        envelope_paths = write_envelope_artifacts(run_dir, fail_envelope)

        set_trace(
            manifest,
            inputs=[str(p) for p in inputs],
            actions=actions + ["Workflow execution failed"],
            outputs=[
                str((run_dir / "outputs" / "runner.json").resolve()),
                envelope_paths["json"],
                envelope_paths["markdown"],
            ],
            assumptions=["Failure captured deterministically in runner.json"],
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        trace_md = render_execution_trace(
            inputs=[str(p) for p in inputs],
            actions=actions + ["Workflow execution failed"],
            outputs=[
                str((run_dir / "outputs" / "runner.json").resolve()),
                envelope_paths["json"],
                envelope_paths["markdown"],
            ],
            assumptions=["Failure captured deterministically in runner.json"],
        )
        write_text(run_dir / "logs" / "execution_trace.md", trace_md)

        summary = render_operator_summary(
            run_id=manifest.get("run_id", run_dir.name),
            workflow=args.workflow,
            status="failed",
            notes=[f"Workflow failed: {exc}"],
        )
        write_text(run_dir / "operator_summary.md", summary)

        print(f"ERROR: workflow failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
