#!/usr/bin/env python3
"""
Guarded operator wrapper: optional CSV snapshot load, Postgres truth-layer validation,
and delegation to the Metabase publisher. Schedule logic stays in SQL/Postgres only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from operator_envelope import build_envelope, write_envelope_artifacts

DEFAULT_AUDIT_DIR = REPO_ROOT / "runtime" / "operator_audit"
DEFAULT_LOAD_SCRIPT = REPO_ROOT / "scripts" / "phase2_load_and_signals.sh"
DEFAULT_PUBLISH_SCRIPT = REPO_ROOT / "scripts" / "publish_recently_slipped_metabase.py"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _audit_timestamp(dt: datetime) -> str:
    """Filesystem-safe UTC timestamp, e.g. 2026-04-13T20-15-30Z."""
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
class SubprocessRecord:
    argv: list[str]
    cwd: str
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None


@dataclass
class CheckRecord:
    id: str
    status: str  # PASS | FAIL | ERROR
    detail: dict[str, Any] = field(default_factory=dict)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "OpenClaw-ready snapshot cycle: optional load (bash pipeline), "
            "Postgres validation, Metabase publish. Truth layer remains PostgreSQL."
        )
    )
    p.add_argument(
        "--snapshot-date",
        metavar="YYYY-MM-DD",
        help="Snapshot date passed to the loader as SNAPSHOT_DATE (required unless --skip-load).",
    )
    p.add_argument(
        "--load-label",
        help="Load label passed to the loader as LOAD_LABEL (required unless --skip-load).",
    )
    p.add_argument(
        "--csv-path",
        type=Path,
        help="CSV file for the loader (exported as CSV_LOCAL; default from loader script).",
    )
    p.add_argument("--skip-load", action="store_true", help="Skip phase2_load_and_signals.sh.")
    p.add_argument("--skip-publish", action="store_true", help="Skip Metabase publisher.")
    p.add_argument(
        "--publish-dry-run",
        action="store_true",
        help="Pass --dry-run to publish_recently_slipped_metabase.py.",
    )
    p.add_argument(
        "--audit-dir",
        type=Path,
        default=DEFAULT_AUDIT_DIR,
        help=f"Directory for JSON audit logs (default: {DEFAULT_AUDIT_DIR}).",
    )
    p.add_argument(
        "--metabase-env-file",
        type=Path,
        help="Optional --env-file for the Metabase publisher (KEY=VALUE).",
    )
    p.add_argument(
        "--database-url",
        "--db-url",
        dest="database_url",
        metavar="URL",
        help="Postgres connection URI for validation queries (psql). "
        "Precedence over Docker: CLI > OPERATOR_DATABASE_URL > DATABASE_URL. When set, Docker container flags are ignored for validation.",
    )
    p.add_argument(
        "--db-container",
        "--postgres-container",
        dest="db_container",
        metavar="NAME",
        help=(
            "Postgres Docker container name for validation (and load unless --db-container-for-load). "
            "When omitted: OPERATOR_DB_CONTAINER env, else auto-discover a single running name equal "
            "to bratek-phase1-postgres or suffixed as <project>_bratek-phase1-postgres, "
            "else default bratek-phase1-postgres. Ignored when a database URL is set (URI mode)."
        ),
    )
    p.add_argument(
        "--db-user",
        default=os.environ.get("OPERATOR_DB_USER", "bratek_ops"),
        help="Postgres user inside --db-container (default: bratek_ops).",
    )
    p.add_argument(
        "--db-name",
        default=os.environ.get("OPERATOR_DB_NAME", "postgres"),
        help="Postgres database inside --db-container (default: postgres).",
    )
    p.add_argument(
        "--db-container-for-load",
        metavar="NAME",
        help="DB_CONTAINER env for the loader only (defaults to same as validation container logic).",
    )
    p.add_argument(
        "--load-script",
        type=Path,
        default=DEFAULT_LOAD_SCRIPT,
        help="Path to phase2_load_and_signals.sh.",
    )
    p.add_argument(
        "--publish-script",
        type=Path,
        default=DEFAULT_PUBLISH_SCRIPT,
        help="Path to publish_recently_slipped_metabase.py.",
    )
    p.add_argument("--verbose", action="store_true", help="Print high-signal progress to stderr.")
    return p.parse_args(argv)


def _log(verbose: bool, msg: str) -> None:
    if verbose:
        print(msg, file=sys.stderr)


def resolve_database_url(args: argparse.Namespace) -> tuple[Optional[str], str]:
    """
    Returns (url_or_none, precedence_note) for audit.
    Precedence: CLI --database-url > OPERATOR_DATABASE_URL > DATABASE_URL.
    """
    if args.database_url:
        return str(args.database_url).strip(), "argv --database-url / --db-url"
    for key in ("OPERATOR_DATABASE_URL", "DATABASE_URL"):
        v = os.environ.get(key, "").strip()
        if v:
            return v, f"environment {key}"
    return None, "not_set"


def discover_postgres_container(preferred: str = "bratek-phase1-postgres") -> tuple[Optional[str], str]:
    """
    If the compose-stable name is not running, accept a single Docker Compose
    project-prefixed name (e.g. 9e60004df82e_bratek-phase1-postgres).

    Returns (resolved_name_or_none, discovery_note) where None means caller
    should fall back to `preferred` literally.
    """
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return None, "docker not in PATH; cannot auto-discover container"
    try:
        proc = subprocess.run(
            [docker_bin, "ps", "--format", "{{.Names}}"],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return None, f"docker ps failed: {type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        return None, f"docker ps exit {proc.returncode}: {(proc.stderr or '').strip()[:500]}"

    names = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if preferred in names:
        return preferred, f"running container name matches compose default {preferred!r}"

    suffix = "_" + preferred
    matches = [n for n in names if n.endswith(suffix) or n == preferred]
    if len(matches) == 1:
        return matches[0], f"auto-selected single running name matching *{suffix!r} pattern"
    if len(matches) > 1:
        return None, f"ambiguous: multiple containers match {preferred!r}: {matches!r}"
    return None, f"no running container named {preferred!r} or *{suffix!r} among {len(names)} running"


def classify_db_failure(
    *,
    transport: str,
    returncode: int,
    stderr: str,
    stdout: str,
) -> str:
    """Operator-facing category for audit/console (not schedule semantics)."""
    err = (stderr or "") + "\n" + (stdout or "")
    el = err.lower()
    if transport == "psql_uri":
        if returncode == 127 or "psql not found" in (stderr or ""):
            return "missing_psql"
        if "could not connect" in el or "connection refused" in el or "timeout expired" in el:
            return "db_connection_failure"
        if "fatal:" in el or "password authentication failed" in el:
            return "db_connection_failure"
        if returncode != 0:
            return "postgres_sql_or_client_error"
        return "ok"

    if transport == "docker_exec":
        if returncode == 127 or "docker not found" in (stderr or ""):
            return "missing_docker"
        if "no such container" in el or "does not exist" in el:
            return "missing_docker_container"
        if "is not running" in el:
            return "docker_container_not_running"
        if "permission denied" in el or "connect: permission denied" in el:
            return "docker_permission_error"
        if "fatal:" in el or "password authentication failed" in el:
            return "db_connection_failure"
        if returncode != 0:
            return "postgres_sql_or_client_error"
        return "ok"

    return "unknown_transport_error"


def run_psql(
    sql: str,
    *,
    database_url: Optional[str],
    db_container: Optional[str],
    db_user: str,
    db_name: str,
    verbose: bool,
) -> tuple[int, str, str, str]:
    """Run a single SQL statement; returns (returncode, stdout, stderr, failure_category)."""
    psql_bin = shutil.which("psql")
    if database_url:
        if not psql_bin:
            return 127, "", "psql not found in PATH (required for --database-url validation)", "missing_psql"
        cmd = [psql_bin, database_url, "-v", "ON_ERROR_STOP=1", "-At", "-c", sql]
        _log(verbose, f"[validation] psql -At -c <{len(sql)} chars>")
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True)
        cat = classify_db_failure(
            transport="psql_uri",
            returncode=proc.returncode,
            stderr=proc.stderr or "",
            stdout=proc.stdout or "",
        )
        return proc.returncode, proc.stdout or "", proc.stderr or "", cat

    if not db_container:
        return 127, "", "No database_url and no db_container for validation", "wrapper_configuration_error"

    docker_bin = shutil.which("docker")
    if not docker_bin:
        return 127, "", "docker not found in PATH (required for --db-container validation)", "missing_docker"
    cmd = [
        docker_bin,
        "exec",
        "-i",
        db_container,
        "psql",
        "-U",
        db_user,
        "-d",
        db_name,
        "-v",
        "ON_ERROR_STOP=1",
        "-At",
        "-c",
        sql,
    ]
    _log(verbose, f"[validation] docker exec {db_container} psql -At -c <{len(sql)} chars>")
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True)
    cat = classify_db_failure(
        transport="docker_exec",
        returncode=proc.returncode,
        stderr=proc.stderr or "",
        stdout=proc.stdout or "",
    )
    return proc.returncode, proc.stdout or "", proc.stderr or "", cat


def run_load(
    args: argparse.Namespace,
    *,
    csv_local: Optional[Path],
    db_container_for_load: Optional[str],
    verbose: bool,
) -> SubprocessRecord:
    env = os.environ.copy()
    env["SNAPSHOT_DATE"] = args.snapshot_date
    env["LOAD_LABEL"] = args.load_label
    if csv_local is not None:
        env["CSV_LOCAL"] = str(csv_local.resolve())
    if db_container_for_load:
        env["DB_CONTAINER"] = db_container_for_load
    script = args.load_script.resolve()
    rec = SubprocessRecord(argv=["bash", str(script)], cwd=str(REPO_ROOT))
    _log(verbose, f"[load] bash {script}")
    try:
        proc = subprocess.run(
            rec.argv,
            cwd=rec.cwd,
            env=env,
            text=True,
            capture_output=True,
        )
        rec.exit_code = proc.returncode
        rec.stdout = proc.stdout or ""
        rec.stderr = proc.stderr or ""
    except Exception as exc:  # noqa: BLE001 — audit boundary
        rec.error = f"{type(exc).__name__}: {exc}"
        rec.exit_code = 1
    return rec


def run_publish(args: argparse.Namespace, verbose: bool) -> SubprocessRecord:
    cmd: list[str] = [sys.executable, str(args.publish_script.resolve())]
    if args.metabase_env_file:
        cmd.extend(["--env-file", str(args.metabase_env_file.resolve())])
    if args.publish_dry_run:
        cmd.append("--dry-run")
    rec = SubprocessRecord(argv=cmd, cwd=str(REPO_ROOT))
    _log(verbose, f"[publish] {' '.join(cmd)}")
    try:
        proc = subprocess.run(
            rec.argv,
            cwd=rec.cwd,
            env=os.environ.copy(),
            text=True,
            capture_output=True,
        )
        rec.exit_code = proc.returncode
        rec.stdout = proc.stdout or ""
        rec.stderr = proc.stderr or ""
    except Exception as exc:  # noqa: BLE001
        rec.error = f"{type(exc).__name__}: {exc}"
        rec.exit_code = 1
    return rec


def preflight_validation(
    *,
    database_url: Optional[str],
    db_container: Optional[str],
    db_user: str,
    db_name: str,
    verbose: bool,
) -> tuple[bool, dict[str, Any]]:
    """Single SELECT 1 to distinguish transport failures from SQL truth checks."""
    rc, out, err, cat = run_psql(
        "SELECT 1;",
        database_url=database_url,
        db_container=db_container,
        db_user=db_user,
        db_name=db_name,
        verbose=verbose,
    )
    ok = rc == 0 and cat == "ok"
    detail: dict[str, Any] = {
        "query": "SELECT 1",
        "exit_code": rc,
        "failure_category": cat,
        "stdout_tail": (out or "")[:500],
        "stderr_tail": (err or "")[-2000:],
    }
    return ok, detail


def validate_truth_layer(
    *,
    database_url: Optional[str],
    db_container: Optional[str],
    db_user: str,
    db_name: str,
    verbose: bool,
) -> tuple[list[CheckRecord], list[str]]:
    errors: list[str] = []
    checks: list[CheckRecord] = []

    def run_check(
        check_id: str,
        sql: str,
        on_result: Callable[[int, str, str], CheckRecord],
    ) -> None:
        rc, out, err, cat = run_psql(
            sql,
            database_url=database_url,
            db_container=db_container,
            db_user=db_user,
            db_name=db_name,
            verbose=verbose,
        )
        if rc != 0:
            msg = err.strip() or out.strip() or f"psql exit {rc}"
            errors.append(f"[sql_validation] {check_id}: {msg}")
            checks.append(
                CheckRecord(
                    check_id,
                    "ERROR",
                    {
                        "exit_code": rc,
                        "stderr": err,
                        "stdout": out,
                        "failure_category": cat,
                    },
                ),
            )
            return
        checks.append(on_result(rc, out, err))

    # 1) Snapshot inventory
    inv_sql = (
        "SELECT snapshot_date::text, COUNT(*)::text FROM schedule_tasks "
        "GROUP BY snapshot_date ORDER BY snapshot_date;"
    )

    def on_inventory(_rc: int, out: str, _err: str) -> CheckRecord:
        rows: list[dict[str, Any]] = []
        for line in out.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 1)
            if len(parts) == 2:
                rows.append({"snapshot_date": parts[0], "row_count": int(parts[1])})
        return CheckRecord(
            "snapshot_inventory_by_date",
            "PASS",
            {"rows": rows},
        )

    run_check("snapshot_inventory_by_date", inv_sql, on_inventory)

    # 2) At least two snapshots
    snap_count_sql = "SELECT COUNT(*) FROM (SELECT DISTINCT snapshot_date FROM schedule_tasks) s;"

    def on_snap_count(_rc: int, out: str, _err: str) -> CheckRecord:
        n = int(out.strip() or "0")
        st = "PASS" if n >= 2 else "FAIL"
        return CheckRecord(
            "at_least_two_snapshots",
            st,
            {"distinct_snapshot_dates": n},
        )

    run_check("at_least_two_snapshots", snap_count_sql, on_snap_count)

    # 3) Duplicates (truth breach if any)
    dup_sql = (
        "SELECT snapshot_date::text, task_id, COUNT(*)::text FROM schedule_tasks "
        "GROUP BY snapshot_date, task_id HAVING COUNT(*) > 1 LIMIT 50;"
    )

    def on_dup(_rc: int, out: str, _err: str) -> CheckRecord:
        bad: list[dict[str, str]] = []
        for line in out.strip().splitlines():
            if not line.strip():
                continue
            bits = line.split("|")
            if len(bits) >= 3:
                bad.append(
                    {"snapshot_date": bits[0], "task_id": bits[1], "count": bits[2]},
                )
        st = "PASS" if not bad else "FAIL"
        return CheckRecord(
            "no_duplicate_snapshot_task_pairs",
            st,
            {"duplicate_rows_sample": bad, "duplicate_groups": len(bad)},
        )

    run_check("no_duplicate_snapshot_task_pairs", dup_sql, on_dup)

    # 4) Unique constraint uq_schedule_tasks
    uq_sql = (
        "SELECT c.conname FROM pg_constraint c "
        "JOIN pg_class t ON c.conrelid = t.oid "
        "JOIN pg_namespace n ON t.relnamespace = n.oid "
        "WHERE n.nspname = 'public' AND t.relname = 'schedule_tasks' "
        "AND c.contype = 'u' AND c.conname = 'uq_schedule_tasks';"
    )

    def on_uq(_rc: int, out: str, _err: str) -> CheckRecord:
        name = out.strip()
        st = "PASS" if name == "uq_schedule_tasks" else "FAIL"
        return CheckRecord(
            "unique_constraint_uq_schedule_tasks",
            st,
            {"conname": name or None},
        )

    run_check("unique_constraint_uq_schedule_tasks", uq_sql, on_uq)

    # 5) v_schedule_snapshot_pair_latest (bounded)
    pair_sql = "SELECT * FROM v_schedule_snapshot_pair_latest LIMIT 5;"

    def on_pair(_rc: int, out: str, _err: str) -> CheckRecord:
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        return CheckRecord(
            "view_v_schedule_snapshot_pair_latest",
            "PASS",
            {"row_count_returned": len(lines), "sample_tsv_lines": lines[:5]},
        )

    run_check("view_v_schedule_snapshot_pair_latest", pair_sql, on_pair)

    # 6) v_schedule_task_finish_delta_latest_pair
    delta_sql = "SELECT COUNT(*) FROM v_schedule_task_finish_delta_latest_pair;"

    def on_delta(_rc: int, out: str, _err: str) -> CheckRecord:
        n = int(out.strip() or "0")
        return CheckRecord(
            "view_v_schedule_task_finish_delta_latest_pair",
            "PASS",
            {"row_count": n},
        )

    run_check("view_v_schedule_task_finish_delta_latest_pair", delta_sql, on_delta)

    # 7) v_signal_recently_slipped_tasks
    slip_sql = "SELECT COUNT(*) FROM v_signal_recently_slipped_tasks;"

    def on_slip(_rc: int, out: str, _err: str) -> CheckRecord:
        n = int(out.strip() or "0")
        return CheckRecord(
            "view_v_signal_recently_slipped_tasks",
            "PASS",
            {"row_count": n},
        )

    run_check("view_v_signal_recently_slipped_tasks", slip_sql, on_slip)

    # 8) v_schedule_wow_task_delta_latest_pair
    wow_delta_sql = "SELECT COUNT(*) FROM v_schedule_wow_task_delta_latest_pair;"

    def on_wow_delta(_rc: int, out: str, _err: str) -> CheckRecord:
        n = int(out.strip() or "0")
        return CheckRecord(
            "view_v_schedule_wow_task_delta_latest_pair",
            "PASS",
            {"row_count": n},
        )

    run_check("view_v_schedule_wow_task_delta_latest_pair", wow_delta_sql, on_wow_delta)

    # 9) v_schedule_wow_kpi_strip
    wow_kpi_sql = "SELECT COUNT(*) FROM v_schedule_wow_kpi_strip;"

    def on_wow_kpi(_rc: int, out: str, _err: str) -> CheckRecord:
        n = int(out.strip() or "0")
        st = "PASS" if n >= 1 else "FAIL"
        return CheckRecord(
            "view_v_schedule_wow_kpi_strip",
            st,
            {"row_count": n},
        )

    run_check("view_v_schedule_wow_kpi_strip", wow_kpi_sql, on_wow_kpi)

    return checks, errors


def checks_overall(checks: list[CheckRecord]) -> bool:
    return all(c.status == "PASS" for c in checks)


def write_audit(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(document, fh, indent=2, sort_keys=False, default=str)
        fh.write("\n")


def emit_operator_envelope_surface(
    *,
    repo_root: Path,
    audit_doc: dict[str, Any],
    audit_json_path: Optional[Path] = None,
    run_dir: Optional[Path] = None,
) -> Path:
    """Materialize canonical envelope artifacts for the snapshot-cycle operator surface.

    Default location: ``runs/_operator_surface/snapshot_cycle_last`` (durable, alongside ``ci_last``).
    """
    run_id = "snapshot_cycle_last"
    dest = run_dir or (repo_root / "runs" / "_operator_surface" / run_id)
    (dest / "inputs").mkdir(parents=True, exist_ok=True)
    (dest / "outputs").mkdir(parents=True, exist_ok=True)
    (dest / "logs").mkdir(parents=True, exist_ok=True)

    overall = str(audit_doc.get("overall_status", "UNKNOWN"))
    summary = audit_doc.get("summary") or {}
    load_s = summary.get("load_status", audit_doc.get("steps", {}).get("load", {}).get("status"))
    val_s = summary.get("validation_status", audit_doc.get("steps", {}).get("validation", {}).get("status"))
    pub_s = summary.get("publish_status", audit_doc.get("steps", {}).get("publish", {}).get("status"))
    ts_finished = str(audit_doc.get("run_finished_at") or audit_doc.get("run_started_at") or _utc_now().isoformat())
    if ts_finished.endswith("+00:00"):
        ts_finished = ts_finished[:-6] + "Z"
    manifest_status = "completed" if overall == "PASS" else "failed"
    audit_ref = str(audit_json_path.resolve()) if audit_json_path else ""

    manifest = {
        "run_id": run_id,
        "timestamp_utc": ts_finished,
        "phase": "Phase 3",
        "status": manifest_status,
        "contract_version": "1.2.0",
        "system_identity": "Operator Local",
        "workflow_name": "operator_run_snapshot_cycle",
        "operator": "single_user",
        "runner": {"name": "operator_run_snapshot_cycle", "version": "1.0.0"},
        "trace": {
            "inputs": [audit_ref] if audit_ref else [],
            "actions": ["Executed guarded snapshot cycle wrapper (load/validate/publish per CLI)."],
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
            "- Ran `scripts/operator_run_snapshot_cycle.py` (guarded snapshot / truth-layer / publish path).",
            "",
            "## What I found",
            f"- Overall status: **{overall}** (load={load_s}, validation={val_s}, publish={pub_s}).",
            "",
            "## What I created",
            f"- `{dest / 'outputs' / 'operator_envelope.json'}`",
            f"- `{dest / 'outputs' / 'operator_envelope.md'}`",
            "",
            "## What needs review",
            "- If status is not PASS, inspect the JSON audit under `runtime/operator_audit/` and remediation steps in the runbook.",
            "",
            "## Next actions",
            "- Follow `docs/operator_run_snapshot_cycle_runbook.md` for the next operational step.",
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
            "- Finalized snapshot-cycle audit document and emitted canonical operator envelope artifacts.",
            "",
            "## Outputs",
            f"- `{dest / 'outputs' / 'operator_envelope.json'}`",
            f"- `{dest / 'outputs' / 'operator_envelope.md'}`",
            "",
            "## Assumptions",
            "- Envelope fields summarize the audit JSON; detailed evidence remains in the audit file.",
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
        created.insert(0, {"path": audit_ref, "description": "Machine-readable snapshot cycle audit JSON"})

    envelope = build_envelope(
        what_i_did=[
            "Executed `operator_run_snapshot_cycle` guarded wrapper "
            f"({audit_doc.get('execution_mode', 'unknown')}).",
        ],
        what_i_found=[
            f"Overall={overall}; load={load_s}; validation={val_s}; publish={pub_s}.",
            *(err_list[:12] if err_list else ["No wrapper-level errors recorded."]),
        ],
        what_i_created=created,
        what_needs_review=(
            ["Review failure_events and validation details in the audit JSON."]
            if overall != "PASS"
            else ["Confirm operational results match expectations before downstream publishes."]
        ),
        next_actions=(
            ["Remediate failing steps using the snapshot cycle runbook and re-run."]
            if overall != "PASS"
            else ["Continue scheduled operator work per MASTER plan continuity docs."]
        ),
        run={"run_id": run_id, "manifest_path": str((dest / "manifest.json").resolve())},
    )
    write_envelope_artifacts(dest, envelope)
    return dest


def build_audit_document(
    *,
    started: datetime,
    finished: datetime,
    overall: str,
    args_ns: argparse.Namespace,
    execution_mode: str,
    load: dict[str, Any],
    validation: dict[str, Any],
    publish: dict[str, Any],
    errors: list[str],
    cli_argv: list[str],
    effective_db_container: Optional[str],
    connection_resolution: dict[str, Any],
    failure_events: list[dict[str, Any]],
) -> dict[str, Any]:
    inputs = {
        "argv": cli_argv,
        "effective_db_container": effective_db_container,
        "snapshot_date": getattr(args_ns, "snapshot_date", None),
        "load_label": getattr(args_ns, "load_label", None),
        "csv_path": str(args_ns.csv_path) if args_ns.csv_path else None,
        "skip_load": args_ns.skip_load,
        "skip_publish": args_ns.skip_publish,
        "publish_dry_run": args_ns.publish_dry_run,
        "audit_dir": str(args_ns.audit_dir),
        "metabase_env_file": str(args_ns.metabase_env_file) if args_ns.metabase_env_file else None,
        "database_url_set": bool(args_ns.database_url or os.environ.get("OPERATOR_DATABASE_URL") or os.environ.get("DATABASE_URL")),
        "db_container": getattr(args_ns, "db_container", None),
        "db_user": args_ns.db_user,
        "db_name": args_ns.db_name,
        "load_script": str(args_ns.load_script),
        "publish_script": str(args_ns.publish_script),
        "verbose": args_ns.verbose,
    }
    summary = {
        "overall_status": overall,
        "load_status": load.get("status"),
        "validation_status": validation.get("status"),
        "publish_status": publish.get("status"),
    }
    return {
        "run_started_at": started.isoformat(),
        "run_finished_at": finished.isoformat(),
        "overall_status": overall,
        "execution_mode": execution_mode,
        "inputs": inputs,
        "connection_resolution": connection_resolution,
        "failure_events": failure_events,
        "steps": {
            "load": load,
            "validation": validation,
            "publish": publish,
        },
        "summary": summary,
        "errors": errors,
    }


def main(argv: list[str]) -> int:
    started = _utc_now()
    errors: list[str] = []
    audit_path: Optional[Path] = None
    args = parse_args(argv)
    failure_events: list[dict[str, Any]] = []

    def finish(
        overall: str,
        *,
        load_block: dict[str, Any],
        validation_block: dict[str, Any],
        publish_block: dict[str, Any],
        execution_mode: str,
        effective_db_container: Optional[str],
        connection_resolution: dict[str, Any],
    ) -> int:
        nonlocal errors, audit_path, failure_events
        finished = _utc_now()
        audit_path = args.audit_dir / f"operator_run_snapshot_cycle_{_audit_timestamp(started)}.json"
        doc = build_audit_document(
            started=started,
            finished=finished,
            overall=overall,
            args_ns=args,
            execution_mode=execution_mode,
            load=load_block,
            validation=validation_block,
            publish=publish_block,
            errors=errors,
            cli_argv=sys.argv,
            effective_db_container=effective_db_container,
            connection_resolution=connection_resolution,
            failure_events=list(failure_events),
        )
        try:
            write_audit(audit_path, _json_safe(doc))
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: cannot write audit log: {exc}", file=sys.stderr)
            return 1
        try:
            emit_operator_envelope_surface(
                repo_root=REPO_ROOT,
                audit_doc=doc,
                audit_json_path=audit_path,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: cannot write operator envelope surface: {exc}", file=sys.stderr)
            return 1
        print(f"OVERALL_STATUS: {overall}")
        if overall != "PASS":
            if failure_events:
                fe = failure_events[0]
                print(
                    f"PRIMARY_FAILURE: scope={fe.get('scope')} category={fe.get('category')}",
                    file=sys.stderr,
                )
            else:
                print("PRIMARY_FAILURE: see audit steps.validation / steps.publish", file=sys.stderr)
        print(f"Audit written: {audit_path}")
        return 0 if overall == "PASS" else 1

    load_block: dict[str, Any] = {"invoked": False, "status": "SKIPPED", "subprocess": None}
    validation_block: dict[str, Any] = {"status": "PENDING", "checks": []}
    publish_block: dict[str, Any] = {"invoked": False, "status": "SKIPPED", "subprocess": None}

    execution_parts: list[str] = []
    if not args.skip_load:
        execution_parts.append("load")
    execution_parts.append("validate")
    if not args.skip_publish:
        execution_parts.append("publish")
    execution_mode = "+".join(execution_parts)

    # --- Load prerequisites ---
    if not args.skip_load:
        if not args.snapshot_date or not args.load_label:
            errors.append("When load is enabled, --snapshot-date and --load-label are required.")
            failure_events.append(
                {
                    "scope": "wrapper",
                    "category": "configuration_error",
                    "message": "missing --snapshot-date or --load-label while load enabled",
                    "detail": {},
                },
            )
            overall = "FAIL"
            load_block = {
                "invoked": False,
                "status": "FAIL",
                "reason": "missing snapshot_date or load_label",
                "subprocess": None,
            }
            validation_block = {"status": "SKIPPED", "checks": [], "reason": "prior failure"}
            publish_block = {
                "invoked": False,
                "status": "SKIPPED",
                "reason": "configuration error before pipeline",
                "subprocess": None,
            }
            return finish(
                overall,
                load_block=load_block,
                validation_block=validation_block,
                publish_block=publish_block,
                execution_mode=execution_mode,
                effective_db_container=None,
                connection_resolution={
                    "validation_transport": "not_evaluated",
                    "note": "aborted before database connection resolution",
                },
            )

    # --- Resolve DB for validation (after load flags validated) ---
    db_url, url_prec = resolve_database_url(args)
    db_container: Optional[str] = None
    container_resolution_note = ""

    if db_url:
        container_resolution_note = "not_applicable: psql URI mode (database URL takes precedence over Docker)"
    else:
        if args.db_container:
            db_container = args.db_container
            container_resolution_note = "argv --db-container / --postgres-container"
        else:
            env_c = os.environ.get("OPERATOR_DB_CONTAINER", "").strip()
            if env_c:
                db_container = env_c
                container_resolution_note = "environment OPERATOR_DB_CONTAINER"
            else:
                discovered, disc_note = discover_postgres_container()
                if discovered:
                    db_container = discovered
                    container_resolution_note = f"auto_discover: {disc_note}"
                else:
                    db_container = "bratek-phase1-postgres"
                    container_resolution_note = f"fallback_literal {db_container!r}: {disc_note}"

    effective_db_container: Optional[str] = None if db_url else db_container
    connection_resolution: dict[str, Any] = {
        "validation_transport": "psql_uri" if db_url else "docker_exec",
        "database_url_resolution": url_prec,
        "postgres_container_resolution": container_resolution_note,
        "effective_postgres_container": effective_db_container,
    }

    # --- Load ---
    if not args.skip_load:
        load_block["invoked"] = True
        csv_path = args.csv_path
        db_load = args.db_container_for_load or db_container
        rec = run_load(args, csv_local=csv_path, db_container_for_load=db_load, verbose=args.verbose)
        load_block["subprocess"] = {
            "argv": rec.argv,
            "cwd": rec.cwd,
            "exit_code": rec.exit_code,
            "stdout_tail": rec.stdout[-8000:] if rec.stdout else "",
            "stderr_tail": rec.stderr[-8000:] if rec.stderr else "",
            "error": rec.error,
        }
        if rec.error or (rec.exit_code is not None and rec.exit_code != 0):
            load_block["status"] = "FAIL"
            errors.append("[load_subprocess] phase2_load_and_signals.sh exited non-zero or raised.")
            failure_events.append(
                {
                    "scope": "load",
                    "category": "load_subprocess_failed",
                    "message": "bash loader failed",
                    "detail": {
                        "exit_code": rec.exit_code,
                        "wrapper_exception": rec.error,
                    },
                },
            )
            overall = "FAIL"
            validation_block = {"status": "SKIPPED", "checks": [], "reason": "load failed"}
            if not args.skip_publish:
                publish_block = {"invoked": False, "status": "SKIPPED", "reason": "load failed", "subprocess": None}
            return finish(
                overall,
                load_block=load_block,
                validation_block=validation_block,
                publish_block=publish_block,
                execution_mode=execution_mode,
                effective_db_container=effective_db_container,
                connection_resolution=connection_resolution,
            )
        load_block["status"] = "PASS"

    # --- Validation ---
    conn_embed = {
        "mode": "psql_uri" if db_url else "docker_exec",
        "database_url_set": bool(db_url),
        "db_container": db_container if not db_url else None,
    }
    try:
        pf_ok, pf_detail = preflight_validation(
            database_url=db_url,
            db_container=db_container,
            db_user=args.db_user,
            db_name=args.db_name,
            verbose=args.verbose,
        )
        if not pf_ok:
            cat = str(pf_detail.get("failure_category", "unknown"))
            errors.append(f"[validation_preflight] {cat}: {(pf_detail.get('stderr_tail') or '').strip()[:400]}")
            failure_events.append(
                {
                    "scope": "validation_preflight",
                    "category": cat,
                    "message": "SELECT 1 failed before truth-layer SQL checks",
                    "detail": pf_detail,
                },
            )
            validation_block = {
                "status": "FAIL",
                "preflight": pf_detail,
                "checks": [],
                "connection": conn_embed,
            }
        else:
            checks, val_errors = validate_truth_layer(
                database_url=db_url,
                db_container=db_container,
                db_user=args.db_user,
                db_name=args.db_name,
                verbose=args.verbose,
            )
            errors.extend(val_errors)
            truth_ok = checks_overall(checks) and not val_errors
            if not truth_ok:
                for c in checks:
                    if c.status == "FAIL":
                        failure_events.append(
                            {
                                "scope": "validation_sql",
                                "category": "truth_layer_check_failed",
                                "message": f"check_id={c.id}",
                                "detail": c.detail,
                            },
                        )
                    elif c.status == "ERROR":
                        failure_events.append(
                            {
                                "scope": "validation_sql",
                                "category": str(c.detail.get("failure_category") or "postgres_sql_or_client_error"),
                                "message": f"check_id={c.id}",
                                "detail": c.detail,
                            },
                        )
            validation_block = {
                "preflight": pf_detail,
                "status": "PASS" if truth_ok else "FAIL",
                "checks": [c.__dict__ for c in checks],
                "connection": conn_embed,
            }
    except Exception as exc:  # noqa: BLE001
        errors.append(f"[wrapper] validation_exception: {type(exc).__name__}: {exc}")
        errors.append(traceback.format_exc())
        failure_events.append(
            {
                "scope": "wrapper",
                "category": "validation_python_exception",
                "message": str(exc),
                "detail": {"type": type(exc).__name__},
            },
        )
        validation_block = {
            "status": "ERROR",
            "checks": [],
            "exception": str(exc),
            "connection": conn_embed,
        }

    if validation_block.get("status") != "PASS":
        overall = "FAIL"
        if not args.skip_publish:
            publish_block = {
                "invoked": False,
                "status": "SKIPPED",
                "reason": "validation did not pass",
                "subprocess": None,
            }
        return finish(
            overall,
            load_block=load_block,
            validation_block=validation_block,
            publish_block=publish_block,
            execution_mode=execution_mode,
            effective_db_container=effective_db_container,
            connection_resolution=connection_resolution,
        )

    # --- Publish ---
    if args.skip_publish:
        publish_block = {"invoked": False, "status": "SKIPPED", "subprocess": None}
        overall = "PASS"
        return finish(
            overall,
            load_block=load_block,
            validation_block=validation_block,
            publish_block=publish_block,
            execution_mode=execution_mode,
            effective_db_container=effective_db_container,
            connection_resolution=connection_resolution,
        )

    publish_block["invoked"] = True
    prec = run_publish(args, args.verbose)
    publish_block["subprocess"] = {
        "argv": prec.argv,
        "cwd": prec.cwd,
        "exit_code": prec.exit_code,
        "stdout_tail": prec.stdout[-12000:] if prec.stdout else "",
        "stderr_tail": prec.stderr[-12000:] if prec.stderr else "",
        "error": prec.error,
        "dry_run": bool(args.publish_dry_run),
    }
    if prec.error or (prec.exit_code is not None and prec.exit_code != 0):
        publish_block["status"] = "FAIL"
        errors.append("[publisher_subprocess] publish_recently_slipped_metabase.py exited non-zero or raised.")
        failure_events.append(
            {
                "scope": "publish",
                "category": "publisher_subprocess_failed",
                "message": "Metabase publisher subprocess failed",
                "detail": {
                    "exit_code": prec.exit_code,
                    "wrapper_exception": prec.error,
                    "stderr_tail": (prec.stderr or "")[-4000:],
                    "stdout_tail": (prec.stdout or "")[-4000:],
                },
            },
        )
        overall = "FAIL"
    else:
        publish_block["status"] = "PASS"
        overall = "PASS"

    return finish(
        overall,
        load_block=load_block,
        validation_block=validation_block,
        publish_block=publish_block,
        execution_mode=execution_mode,
        effective_db_container=effective_db_container,
        connection_resolution=connection_resolution,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
