#!/usr/bin/env python3
"""
Guarded financial operator cycle: optional SQL apply, Postgres view validation,
Metabase financial publisher, optional manifest load. Writes JSON audit under runtime/operator_audit/.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from operator_envelope import build_envelope, write_envelope_artifacts
DEFAULT_AUDIT_DIR = REPO_ROOT / "runtime" / "operator_audit"
APPLY_SCRIPT = REPO_ROOT / "scripts" / "apply_financial_sql.sh"
VALIDATE_SCRIPT = REPO_ROOT / "scripts" / "validate_financial_views.py"
PUBLISH_SCRIPT = REPO_ROOT / "scripts" / "publish_financial_control_loop_metabase.py"
MANIFEST_LOADER = REPO_ROOT / "scripts" / "load_financial_manifest.py"


def resolve_financial_metabase_env_file(explicit: Optional[Path]) -> tuple[Optional[Path], list[str]]:
    """
    Find Metabase env file without requiring admin: repo config/, env vars, or ~/.config.
    Returns (path_or_none, list of paths tried for error messages).
    """
    tried: list[str] = []
    if explicit is not None:
        p = explicit.expanduser().resolve()
        tried.append(f"{p} ({'ok' if p.is_file() else 'missing'})")
        return (p if p.is_file() else None, tried)

    for key in ("METABASE_FINANCIAL_ENV_FILE", "METABASE_PUBLISH_ENV_FILE"):
        raw = os.environ.get(key, "").strip()
        if not raw:
            continue
        p = Path(raw).expanduser().resolve()
        tried.append(f"{key} -> {p} ({'ok' if p.is_file() else 'missing'})")
        if p.is_file():
            return p, tried

    for rel in (
        REPO_ROOT / "config" / "metabase_publish.financial.env",
        REPO_ROOT / "config" / "metabase_publish.env",
        Path.home() / ".config" / "bratek" / "metabase_publish.env",
    ):
        p = rel.expanduser().resolve()
        tried.append(f"{p} ({'ok' if p.is_file() else 'missing'})")
        if p.is_file():
            return p, tried

    return None, tried


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _audit_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H-%M-%SZ")


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj


@dataclass
class SubRecord:
    argv: list[str]
    cwd: str
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None


def write_audit(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=False, default=str)
        fh.write("\n")


def _financial_steps_summary(audit_doc: dict[str, Any]) -> str:
    steps = audit_doc.get("steps") or {}
    if not isinstance(steps, dict):
        return "(no steps)"
    parts: list[str] = []
    for key in ("load_manifest", "apply_sql", "preflight", "validate", "publish"):
        blk = steps.get(key)
        if not blk or not isinstance(blk, dict):
            continue
        ec = blk.get("exit_code")
        err = blk.get("error")
        tail = f" error={err}" if err else ""
        parts.append(f"{key}: exit_code={ec}{tail}")
    return "; ".join(parts) if parts else "(no step records)"


def emit_operator_envelope_financial_surface(
    *,
    repo_root: Path,
    audit_doc: dict[str, Any],
    audit_json_path: Optional[Path] = None,
    run_dir: Optional[Path] = None,
) -> Path:
    """Materialize canonical envelope artifacts for the financial-cycle operator surface.

    Default location: ``runs/_operator_surface/financial_cycle_last``.
    """
    run_id = "financial_cycle_last"
    dest = run_dir or (repo_root / "runs" / "_operator_surface" / run_id)
    (dest / "inputs").mkdir(parents=True, exist_ok=True)
    (dest / "outputs").mkdir(parents=True, exist_ok=True)
    (dest / "logs").mkdir(parents=True, exist_ok=True)

    overall = str(audit_doc.get("overall_status", "UNKNOWN"))
    cmd = str(audit_doc.get("command", "unknown"))
    ts_finished = str(audit_doc.get("run_finished_at") or audit_doc.get("run_started_at") or _utc_now().isoformat())
    if ts_finished.endswith("+00:00"):
        ts_finished = ts_finished[:-6] + "Z"
    manifest_status = "completed" if overall == "PASS" else "failed"
    audit_ref = str(audit_json_path.resolve()) if audit_json_path else ""
    step_line = _financial_steps_summary(audit_doc)
    failure = audit_doc.get("failure")

    manifest = {
        "run_id": run_id,
        "timestamp_utc": ts_finished,
        "phase": "Phase 3",
        "status": manifest_status,
        "contract_version": "1.2.0",
        "system_identity": "Operator Local",
        "workflow_name": "operator_run_financial_cycle",
        "operator": "single_user",
        "runner": {"name": "operator_run_financial_cycle", "version": "1.0.0"},
        "trace": {
            "inputs": [audit_ref] if audit_ref else [],
            "actions": [f"Executed financial operator cycle subcommand `{cmd}`."],
            "outputs": [
                str((dest / "outputs" / "operator_envelope.json").resolve()),
                str((dest / "outputs" / "operator_envelope.md").resolve()),
            ],
            "assumptions": [
                "Canonical operator narrative for this surface is the envelope artifacts under outputs/.",
            ],
        },
        "artifacts": {
            "operator_summary": "operator_summary.md",
            "inputs_dir": "inputs/",
            "outputs_dir": "outputs/",
            "logs_dir": "logs/",
        },
        "review": {"needs_review": overall != "PASS", "review_notes": list(audit_doc.get("errors") or [])},
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    summary_md = "\n".join(
        [
            f"# Operator Summary — {run_id}",
            "",
            "## What I did",
            "- Ran `scripts/operator_run_financial_cycle.py` (guarded financial SQL / validation / Metabase path).",
            "",
            "## What I found",
            f"- Subcommand `{cmd}`; overall **{overall}**.",
            f"- Steps: {step_line}",
            "",
            "## What I created",
            f"- `{dest / 'outputs' / 'operator_envelope.json'}`",
            f"- `{dest / 'outputs' / 'operator_envelope.md'}`",
            "",
            "## What needs review",
            "- If status is not PASS, inspect the JSON audit under `runtime/operator_audit/` and `docs/financial_control_loop_runbook.md`.",
            "",
            "## Next actions",
            "- Follow the financial production checklist and runbook for remediation or the next cycle step.",
            "",
        ]
    )
    (dest / "operator_summary.md").write_text(summary_md, encoding="utf-8")

    trace_md = "\n".join(
        [
            f"# Execution Trace — {run_id}",
            "",
            "## Inputs",
            f"- `{'audit JSON: ' + audit_ref if audit_ref else '(no audit path recorded)'}`",
            "",
            "## Actions",
            "- Finalized financial-cycle audit document and emitted canonical operator envelope artifacts.",
            "",
            "## Outputs",
            f"- `{dest / 'outputs' / 'operator_envelope.json'}`",
            f"- `{dest / 'outputs' / 'operator_envelope.md'}`",
            "",
            "## Assumptions",
            "- Envelope summarizes the audit JSON; subprocess evidence remains in the audit file.",
            "",
        ]
    ).rstrip() + "\n"
    (dest / "logs" / "execution_trace.md").write_text(trace_md, encoding="utf-8")

    err_list = list(audit_doc.get("errors") or [])
    created = [
        {
            "path": str((dest / "outputs" / "operator_envelope.json").resolve()),
            "description": "Canonical operator envelope JSON",
        },
        {
            "path": str((dest / "outputs" / "operator_envelope.md").resolve()),
            "description": "Canonical operator envelope markdown",
        },
    ]
    if audit_ref:
        created.insert(0, {"path": audit_ref, "description": "Machine-readable financial cycle audit JSON"})

    finding = [
        f"command={cmd}; overall={overall}.",
        f"Steps: {step_line}.",
    ]
    if failure:
        finding.append(f"failure={failure}.")
    if audit_doc.get("exception"):
        finding.append("Python exception recorded in audit (see audit JSON).")
    finding.extend(err_list[:10] if err_list else ["No wrapper-level errors recorded."])

    envelope = build_envelope(
        what_i_did=[f"Executed `operator_run_financial_cycle` subcommand `{cmd}`."],
        what_i_found=finding,
        what_i_created=created,
        what_needs_review=(
            ["Review audit steps, Metabase env resolution, and subprocess stderr in the audit JSON."]
            if overall != "PASS"
            else ["Confirm financial views and published dashboards match operational intent."]
        ),
        next_actions=(
            ["Remediate using docs/financial_control_loop_runbook.md and re-run."]
            if overall != "PASS"
            else ["Continue the financial control loop per production checklist."]
        ),
        run={"run_id": run_id, "manifest_path": str((dest / "manifest.json").resolve())},
    )
    write_envelope_artifacts(dest, envelope)
    return dest


def run_subprocess(argv: list[str], *, cwd: str) -> SubRecord:
    rec = SubRecord(argv=argv, cwd=cwd)
    try:
        proc = subprocess.run(argv, cwd=cwd, text=True, capture_output=True)
        rec.exit_code = proc.returncode
        rec.stdout = proc.stdout or ""
        rec.stderr = proc.stderr or ""
    except Exception as exc:  # noqa: BLE001
        rec.error = f"{type(exc).__name__}: {exc}"
        rec.exit_code = 1
    return rec


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Financial operator cycle with audit JSON.")
    p.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    p.add_argument("--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("preflight", help="SELECT 1 against Postgres (docker or URI).")
    b.add_argument("--database-url", "--db-url", dest="database_url")
    b.add_argument("--db-container", default=os.environ.get("FINANCIAL_DB_CONTAINER", "bratek-phase1-postgres"))
    b.add_argument("--db-user", default=os.environ.get("FINANCIAL_DB_USER", "bratek_ops"))
    b.add_argument("--db-name", default=os.environ.get("FINANCIAL_DB_NAME", "postgres"))

    sub.add_parser("apply-sql", help=f"Run {APPLY_SCRIPT.name} (docker apply bundle).")

    sub.add_parser(
        "show-metabase-env",
        help="Print which Metabase env file would be used (paths only; does not print secrets).",
    )

    v = sub.add_parser("validate", help="Run validate_financial_views.py")
    v.add_argument("--project-code", help="Require variance rows for this project.")
    v.add_argument("--database-url", "--db-url", dest="database_url")
    v.add_argument("--db-container", default=os.environ.get("FINANCIAL_DB_CONTAINER", "bratek-phase1-postgres"))
    v.add_argument("--db-user", default=os.environ.get("FINANCIAL_DB_USER", "bratek_ops"))
    v.add_argument("--db-name", default=os.environ.get("FINANCIAL_DB_NAME", "postgres"))

    pub = sub.add_parser("publish", help="Publish financial Metabase dashboard")
    pub.add_argument(
        "--metabase-env-file",
        type=Path,
        default=None,
        help=(
            "KEY=VALUE or export lines for Metabase. If omitted: METABASE_FINANCIAL_ENV_FILE, "
            "METABASE_PUBLISH_ENV_FILE, then config/metabase_publish.financial.env, "
            "config/metabase_publish.env, ~/.config/bratek/metabase_publish.env (see config/README.md)."
        ),
    )
    pub.add_argument("--dry-run", action="store_true")

    ld = sub.add_parser("load-manifest", help="Delegate to load_financial_manifest.py")
    ld.add_argument("--manifest-path", type=Path, required=True)
    ld.add_argument("--skip-ddl", action="store_true")
    ld.add_argument("--continue-on-error", action="store_true")
    ld.add_argument("--database-url", "--db-url", dest="database_url")
    ld.add_argument("--db-container", default=os.environ.get("FINANCIAL_DB_CONTAINER", "bratek-phase1-postgres"))
    ld.add_argument("--db-user", default=os.environ.get("FINANCIAL_DB_USER", "bratek_ops"))
    ld.add_argument("--db-name", default=os.environ.get("FINANCIAL_DB_NAME", "postgres"))

    run = sub.add_parser("run", help="apply-sql → validate → publish (optional load-manifest first)")
    run.add_argument("--skip-apply-sql", action="store_true")
    run.add_argument("--skip-publish", action="store_true")
    run.add_argument("--publish-dry-run", action="store_true")
    run.add_argument(
        "--metabase-env-file",
        type=Path,
        default=None,
        help="Same as publish; optional unless --skip-publish (default search path applies).",
    )
    run.add_argument("--project-code", help="Passed to validate step")
    run.add_argument("--manifest-path", type=Path, help="If set, load manifest before apply-sql")
    run.add_argument("--manifest-skip-ddl", action="store_true", help="With --manifest-path, pass --skip-ddl to loader")
    run.add_argument("--database-url", "--db-url", dest="database_url")
    run.add_argument("--db-container", default=os.environ.get("FINANCIAL_DB_CONTAINER", "bratek-phase1-postgres"))
    run.add_argument("--db-user", default=os.environ.get("FINANCIAL_DB_USER", "bratek_ops"))
    run.add_argument("--db-name", default=os.environ.get("FINANCIAL_DB_NAME", "postgres"))

    args = p.parse_args(argv)
    return args


def psql_preflight(database_url: Optional[str], db_container: str, db_user: str, db_name: str) -> SubRecord:
    psql = shutil.which("psql")
    if database_url:
        if not psql:
            return SubRecord(argv=[], cwd=str(REPO_ROOT), error="psql missing", exit_code=127)
        return run_subprocess([psql, database_url, "-v", "ON_ERROR_STOP=1", "-At", "-c", "SELECT 1;"], cwd=str(REPO_ROOT))
    docker = shutil.which("docker")
    if not docker:
        return SubRecord(argv=[], cwd=str(REPO_ROOT), error="docker missing", exit_code=127)
    return run_subprocess(
        [docker, "exec", "-i", db_container, "psql", "-U", db_user, "-d", db_name, "-v", "ON_ERROR_STOP=1", "-At", "-c", "SELECT 1;"],
        cwd=str(REPO_ROOT),
    )


def main(argv: list[str]) -> int:
    started = _utc_now()
    args = parse_args(argv)
    audit_path = args.audit_dir / f"operator_run_financial_cycle_{_audit_ts(started)}.json"
    doc: dict[str, Any] = {
        "run_started_at": started.isoformat(),
        "command": args.command,
        "argv": sys.argv,
        "steps": {},
        "overall_status": "PENDING",
    }

    def finish(status: str, extra: Optional[dict[str, Any]] = None) -> int:
        doc["run_finished_at"] = _utc_now().isoformat()
        doc["overall_status"] = status
        if extra:
            doc.update(extra)
        try:
            write_audit(audit_path, _json_safe(doc))
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: audit write failed: {exc}", file=sys.stderr)
            return 1
        try:
            emit_operator_envelope_financial_surface(
                repo_root=REPO_ROOT,
                audit_doc=doc,
                audit_json_path=audit_path,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: cannot write operator envelope surface: {exc}", file=sys.stderr)
            return 1
        print(f"OVERALL_STATUS: {status}")
        print(f"Audit: {audit_path}")
        return 0 if status == "PASS" else 1

    try:
        if args.command == "preflight":
            rec = psql_preflight(
                getattr(args, "database_url", None),
                args.db_container,
                args.db_user,
                args.db_name,
            )
            doc["steps"]["preflight"] = rec.__dict__
            return finish("PASS" if rec.exit_code == 0 and not rec.error else "FAIL")

        if args.command == "apply-sql":
            if not APPLY_SCRIPT.is_file():
                doc["errors"] = ["apply script missing"]
                return finish("FAIL")
            rec = run_subprocess(["bash", str(APPLY_SCRIPT)], cwd=str(REPO_ROOT))
            doc["steps"]["apply_sql"] = rec.__dict__
            return finish("PASS" if rec.exit_code == 0 and not rec.error else "FAIL")

        if args.command == "show-metabase-env":
            resolved, tried = resolve_financial_metabase_env_file(None)
            print("Financial Metabase env — search order (first existing wins):")
            for line in tried:
                print(f"  {line}")
            if resolved:
                print(f"Resolved: {resolved}")
                return 0
            print(
                "No env file found. Add config/metabase_publish.env or set METABASE_FINANCIAL_ENV_FILE.",
                file=sys.stderr,
            )
            return 1

        if args.command == "validate":
            cmd = [sys.executable, str(VALIDATE_SCRIPT)]
            if args.project_code:
                cmd.extend(["--project-code", args.project_code])
            if getattr(args, "database_url", None):
                cmd.extend(["--database-url", args.database_url])
            cmd.extend(["--db-container", args.db_container, "--db-user", args.db_user, "--db-name", args.db_name])
            rec = run_subprocess(cmd, cwd=str(REPO_ROOT))
            doc["steps"]["validate"] = rec.__dict__
            return finish("PASS" if rec.exit_code == 0 and not rec.error else "FAIL")

        if args.command == "publish":
            mb_env, tried = resolve_financial_metabase_env_file(args.metabase_env_file)
            doc["metabase_env_resolution"] = {"path": str(mb_env) if mb_env else None, "candidates": tried}
            if mb_env is None:
                doc["errors"] = [
                    "No Metabase env file found. Create config/metabase_publish.env (see config/README.md) "
                    "or pass --metabase-env-file.",
                ]
                return finish("FAIL", {"failure": "missing_metabase_env"})
            cmd = [sys.executable, str(PUBLISH_SCRIPT), "--env-file", str(mb_env)]
            if args.dry_run:
                cmd.append("--dry-run")
            rec = run_subprocess(cmd, cwd=str(REPO_ROOT))
            doc["steps"]["publish"] = rec.__dict__
            return finish("PASS" if rec.exit_code == 0 and not rec.error else "FAIL")

        if args.command == "load-manifest":
            cmd = [sys.executable, str(MANIFEST_LOADER), "--manifest-path", str(args.manifest_path.resolve())]
            if args.skip_ddl:
                cmd.append("--skip-ddl")
            if args.continue_on_error:
                cmd.append("--continue-on-error")
            if getattr(args, "database_url", None):
                cmd.extend(["--db-url", args.database_url])
            if args.db_container:
                cmd.extend(["--db-container", args.db_container])
            if args.db_user:
                cmd.extend(["--db-user", args.db_user])
            if args.db_name:
                cmd.extend(["--db-name", args.db_name])
            rec = run_subprocess(cmd, cwd=str(REPO_ROOT))
            doc["steps"]["load_manifest"] = rec.__dict__
            return finish("PASS" if rec.exit_code == 0 and not rec.error else "FAIL")

        if args.command == "run":
            steps: dict[str, Any] = {}
            if args.manifest_path:
                lcmd = [sys.executable, str(MANIFEST_LOADER), "--manifest-path", str(args.manifest_path.resolve())]
                if args.manifest_skip_ddl:
                    lcmd.append("--skip-ddl")
                if args.database_url:
                    lcmd.extend(["--db-url", args.database_url])
                lcmd.extend(["--db-container", args.db_container])
                if args.db_user:
                    lcmd.extend(["--db-user", args.db_user])
                if args.db_name:
                    lcmd.extend(["--db-name", args.db_name])
                lrec = run_subprocess(lcmd, cwd=str(REPO_ROOT))
                steps["load_manifest"] = lrec.__dict__
                if lrec.exit_code != 0 or lrec.error:
                    doc["steps"] = steps
                    return finish("FAIL", {"failure": "load_manifest"})

            if not args.skip_apply_sql:
                arec = run_subprocess(["bash", str(APPLY_SCRIPT)], cwd=str(REPO_ROOT))
                steps["apply_sql"] = arec.__dict__
                if arec.exit_code != 0 or arec.error:
                    doc["steps"] = steps
                    return finish("FAIL", {"failure": "apply_sql"})

            vcmd = [sys.executable, str(VALIDATE_SCRIPT), "--db-container", args.db_container, "--db-user", args.db_user, "--db-name", args.db_name]
            if args.project_code:
                vcmd.extend(["--project-code", args.project_code])
            if args.database_url:
                vcmd.extend(["--database-url", args.database_url])
            vrec = run_subprocess(vcmd, cwd=str(REPO_ROOT))
            steps["validate"] = vrec.__dict__
            if vrec.exit_code != 0 or vrec.error:
                doc["steps"] = steps
                return finish("FAIL", {"failure": "validate"})

            if not args.skip_publish:
                mb_env, tried = resolve_financial_metabase_env_file(args.metabase_env_file)
                doc["metabase_env_resolution"] = {"path": str(mb_env) if mb_env else None, "candidates": tried}
                if mb_env is None:
                    doc["steps"] = steps
                    doc["errors"] = [
                        "No Metabase env file found for publish. Set METABASE_FINANCIAL_ENV_FILE, "
                        "add config/metabase_publish.env, or pass --metabase-env-file (see config/README.md).",
                    ]
                    return finish("FAIL", {"failure": "missing_metabase_env"})
                pcmd = [sys.executable, str(PUBLISH_SCRIPT), "--env-file", str(mb_env)]
                if args.publish_dry_run:
                    pcmd.append("--dry-run")
                prec = run_subprocess(pcmd, cwd=str(REPO_ROOT))
                steps["publish"] = prec.__dict__
                if prec.exit_code != 0 or prec.error:
                    doc["steps"] = steps
                    return finish("FAIL", {"failure": "publish"})

            doc["steps"] = steps
            return finish("PASS")

    except Exception as exc:  # noqa: BLE001
        doc["exception"] = traceback.format_exc()
        doc["error_message"] = str(exc)
        doc["run_finished_at"] = _utc_now().isoformat()
        doc["overall_status"] = "ERROR"
        try:
            write_audit(audit_path, _json_safe(doc))
        except Exception as wexc:  # noqa: BLE001
            print(f"ERROR: audit write failed: {wexc}", file=sys.stderr)
            return 1
        try:
            emit_operator_envelope_financial_surface(
                repo_root=REPO_ROOT,
                audit_doc=doc,
                audit_json_path=audit_path,
            )
        except Exception as eexc:  # noqa: BLE001
            print(f"ERROR: cannot write operator envelope surface: {eexc}", file=sys.stderr)
            return 1
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    doc["errors"] = ["unhandled command"]
    return finish("FAIL")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
