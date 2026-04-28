#!/usr/bin/env python3
"""
Weekly operator cycle wrapper.

Orchestration-only boundary:
- PostgreSQL owns schedule/comparison logic.
- This wrapper only coordinates existing load/refresh assets and records audit output.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from operator_envelope import build_envelope, write_envelope_artifacts
DEFAULT_AUDIT_DIR = REPO_ROOT / "runtime" / "operator_audit"
DEFAULT_LOAD_SCRIPT = REPO_ROOT / "scripts" / "phase2_load_and_signals.sh"
SQL_REFRESH_DEP_GRAPH = REPO_ROOT / "sql" / "06_refresh_dependency_graph.sql"
SQL_REFRESH_COMPUTED = REPO_ROOT / "sql" / "07_refresh_computed_driver_path.sql"
SQL_REFRESH_SIGNALS = REPO_ROOT / "sql" / "04_signals.sql"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _audit_stamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H-%M-%SZ")


def _as_jsonable(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _as_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_as_jsonable(v) for v in obj]
    return obj


def _parse_iso_date(value: str, flag_name: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{flag_name} must be YYYY-MM-DD: {value!r}") from exc
    if len(value) != 10:
        raise argparse.ArgumentTypeError(f"{flag_name} must be YYYY-MM-DD: {value!r}")
    return parsed


def emit_operator_envelope_weekly_surface(
    *,
    repo_root: Path,
    audit_doc: dict[str, Any],
    audit_json_path: Optional[Path] = None,
    run_dir: Optional[Path] = None,
) -> Path:
    """Materialize canonical envelope artifacts for the weekly-cycle operator surface.

    Default location: ``runs/_operator_surface/weekly_cycle_last``.
    """
    run_id = "weekly_cycle_last"
    dest = run_dir or (repo_root / "runs" / "_operator_surface" / run_id)
    (dest / "inputs").mkdir(parents=True, exist_ok=True)
    (dest / "outputs").mkdir(parents=True, exist_ok=True)
    (dest / "logs").mkdir(parents=True, exist_ok=True)

    overall = str(audit_doc.get("overall_status", "UNKNOWN"))
    snap = str(audit_doc.get("snapshot_date", ""))
    load_s = str(audit_doc.get("load_status", ""))
    ref_s = str(audit_doc.get("refresh_status", ""))
    val_s = str(audit_doc.get("validation_status", ""))
    ts_finished = str(audit_doc.get("run_finished_at") or audit_doc.get("run_started_at") or _utc_now().isoformat())
    if ts_finished.endswith("+00:00"):
        ts_finished = ts_finished[:-6] + "Z"
    manifest_status = "completed" if overall == "PASS" else "failed"
    audit_ref = str(audit_json_path.resolve()) if audit_json_path else ""
    errs = audit_doc.get("error_messages") or []
    err_list = list(errs) if isinstance(errs, list) else []

    manifest = {
        "run_id": run_id,
        "timestamp_utc": ts_finished,
        "phase": "Phase 3",
        "status": manifest_status,
        "contract_version": "1.2.0",
        "system_identity": "Operator Local",
        "workflow_name": "operator_run_weekly_cycle",
        "operator": "single_user",
        "runner": {"name": "operator_run_weekly_cycle", "version": "1.0.0"},
        "trace": {
            "inputs": [audit_ref] if audit_ref else [],
            "actions": ["Executed weekly operator cycle wrapper (load / SQL refresh / validation)."],
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
        "review": {"needs_review": overall != "PASS", "review_notes": err_list},
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    summary_md = "\n".join(
        [
            f"# Operator Summary — {run_id}",
            "",
            "## What I did",
            "- Ran `scripts/operator_run_weekly_cycle.py` (weekly load / refresh / validation path).",
            "",
            "## What I found",
            f"- Overall **{overall}**; snapshot_date={snap}; load={load_s}; refresh={ref_s}; validation={val_s}.",
            "",
            "## What I created",
            f"- `{dest / 'outputs' / 'operator_envelope.json'}`",
            f"- `{dest / 'outputs' / 'operator_envelope.md'}`",
            "",
            "## What needs review",
            "- If status is not PASS, inspect the JSON audit under `runtime/operator_audit/` and `docs/weekly_operator_cycle_runbook.md`.",
            "",
            "## Next actions",
            "- Follow the weekly operator cycle runbook for remediation or the next cycle.",
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
            "- Finalized weekly-cycle audit document and emitted canonical operator envelope artifacts.",
            "",
            "## Outputs",
            f"- `{dest / 'outputs' / 'operator_envelope.json'}`",
            f"- `{dest / 'outputs' / 'operator_envelope.md'}`",
            "",
            "## Assumptions",
            "- Envelope summarizes the audit JSON; SQL and loader evidence remains in the audit file.",
            "",
        ]
    ).rstrip() + "\n"
    (dest / "logs" / "execution_trace.md").write_text(trace_md, encoding="utf-8")

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
        created.insert(0, {"path": audit_ref, "description": "Machine-readable weekly cycle audit JSON"})

    finding = [
        f"overall={overall}; snapshot_date={snap}; load={load_s}; refresh={ref_s}; validation={val_s}.",
        *(err_list[:12] if err_list else ["No wrapper-level errors recorded."]),
    ]

    envelope = build_envelope(
        what_i_did=["Executed `operator_run_weekly_cycle` guarded weekly wrapper."],
        what_i_found=finding,
        what_i_created=created,
        what_needs_review=(
            ["Review error_messages and validation_checks in the audit JSON."]
            if overall != "PASS"
            else ["Confirm path-comparison URLs and schedule intelligence match operational intent."]
        ),
        next_actions=(
            ["Remediate using docs/weekly_operator_cycle_runbook.md and re-run."]
            if overall != "PASS"
            else ["Continue weekly operator rhythm per continuity docs."]
        ),
        run={"run_id": run_id, "manifest_path": str((dest / "manifest.json").resolve())},
    )
    write_envelope_artifacts(dest, envelope)
    return dest


@dataclass
class CmdResult:
    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str


@dataclass
class DbContext:
    mode: str  # psql_uri | docker_exec
    database_url: Optional[str]
    db_container: Optional[str]
    db_user: str
    db_name: str
    psql_bin: Optional[str]
    docker_bin: Optional[str]
    resolution: dict[str, Any]


def _run_cmd(
    argv: list[str],
    *,
    cwd: Path = REPO_ROOT,
    env: Optional[dict[str, str]] = None,
    stdin_text: Optional[str] = None,
) -> CmdResult:
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        env=env,
        text=True,
        input=stdin_text,
        capture_output=True,
    )
    return CmdResult(
        argv=list(argv),
        exit_code=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def _discover_container_name(docker_bin: str, preferred: str = "bratek-phase1-postgres") -> tuple[Optional[str], str]:
    proc = _run_cmd([docker_bin, "ps", "--format", "{{.Names}}"])
    if proc.exit_code != 0:
        return None, f"docker ps failed: {(proc.stderr or proc.stdout).strip()[:400]}"
    names = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if preferred in names:
        return preferred, f"running container matches {preferred}"
    suffix = "_" + preferred
    matches = [n for n in names if n.endswith(suffix)]
    if len(matches) == 1:
        return matches[0], f"auto-discovered single suffixed name {matches[0]}"
    if len(matches) > 1:
        return None, f"ambiguous discovered containers: {matches}"
    return None, f"no running container matches {preferred} or *{suffix}"


def _resolve_db_context(args: argparse.Namespace) -> DbContext:
    db_url = (args.database_url or os.environ.get("OPERATOR_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()
    psql_bin = shutil.which("psql")
    docker_bin = shutil.which("docker")

    resolution: dict[str, Any] = {
        "database_url_source": None,
        "container_source": None,
    }

    if args.database_url and args.database_url.strip():
        resolution["database_url_source"] = "--database-url"
    elif os.environ.get("OPERATOR_DATABASE_URL", "").strip():
        resolution["database_url_source"] = "OPERATOR_DATABASE_URL"
    elif os.environ.get("DATABASE_URL", "").strip():
        resolution["database_url_source"] = "DATABASE_URL"
    else:
        resolution["database_url_source"] = "not_set"

    if db_url:
        if not psql_bin:
            raise RuntimeError("psql is required for --database-url mode but was not found in PATH")
        return DbContext(
            mode="psql_uri",
            database_url=db_url,
            db_container=None,
            db_user=args.db_user,
            db_name=args.db_name,
            psql_bin=psql_bin,
            docker_bin=docker_bin,
            resolution=resolution,
        )

    if not docker_bin:
        raise RuntimeError("docker is required for container DB mode but was not found in PATH")

    if args.db_container:
        db_container = args.db_container.strip()
        resolution["container_source"] = "--db-container"
    elif os.environ.get("OPERATOR_DB_CONTAINER", "").strip():
        db_container = os.environ["OPERATOR_DB_CONTAINER"].strip()
        resolution["container_source"] = "OPERATOR_DB_CONTAINER"
    else:
        discovered, note = _discover_container_name(docker_bin)
        if discovered:
            db_container = discovered
            resolution["container_source"] = f"auto_discover ({note})"
        else:
            db_container = "bratek-phase1-postgres"
            resolution["container_source"] = f"default_fallback ({note})"

    return DbContext(
        mode="docker_exec",
        database_url=None,
        db_container=db_container,
        db_user=args.db_user,
        db_name=args.db_name,
        psql_bin=psql_bin,
        docker_bin=docker_bin,
        resolution=resolution,
    )


def _run_sql(ctx: DbContext, sql: str) -> CmdResult:
    if ctx.mode == "psql_uri":
        return _run_cmd(
            [
                ctx.psql_bin or "psql",
                ctx.database_url or "",
                "-v",
                "ON_ERROR_STOP=1",
                "-At",
                "-c",
                sql,
            ]
        )
    return _run_cmd(
        [
            ctx.docker_bin or "docker",
            "exec",
            "-i",
            ctx.db_container or "",
            "psql",
            "-U",
            ctx.db_user,
            "-d",
            ctx.db_name,
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-c",
            sql,
        ]
    )


def _run_sql_file(ctx: DbContext, file_path: Path) -> CmdResult:
    if ctx.mode == "psql_uri":
        return _run_cmd(
            [
                ctx.psql_bin or "psql",
                ctx.database_url or "",
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                str(file_path),
            ]
        )
    sql_text = file_path.read_text(encoding="utf-8")
    return _run_cmd(
        [
            ctx.docker_bin or "docker",
            "exec",
            "-i",
            ctx.db_container or "",
            "psql",
            "-U",
            ctx.db_user,
            "-d",
            ctx.db_name,
            "-v",
            "ON_ERROR_STOP=1",
        ],
        stdin_text=sql_text,
    )


def _sql_literal_date(value: date) -> str:
    return f"DATE '{value.isoformat()}'"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Weekly operator cycle wrapper: load -> refresh -> validate -> review links."
    )
    parser.add_argument("--csv", type=Path, required=True, help="Path to weekly schedule export CSV.")
    parser.add_argument(
        "--snapshot-date",
        required=True,
        help="Target snapshot date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--prior-snapshot-date",
        help="Optional explicit prior snapshot baseline (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--skip-load",
        action="store_true",
        help="Skip load step (useful when snapshot already loaded).",
    )
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="Skip SQL refresh step.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation checks.",
    )
    parser.add_argument(
        "--database-url",
        "--db-url",
        dest="database_url",
        help="Optional postgres URL (psql mode).",
    )
    parser.add_argument(
        "--db-container",
        "--postgres-container",
        dest="db_container",
        help="Postgres container name for docker exec mode.",
    )
    parser.add_argument("--db-user", default=os.environ.get("OPERATOR_DB_USER", "bratek_ops"))
    parser.add_argument("--db-name", default=os.environ.get("OPERATOR_DB_NAME", "postgres"))
    parser.add_argument(
        "--db-container-for-load",
        help="Optional load-only DB_CONTAINER override for phase2_load_and_signals.sh.",
    )
    parser.add_argument(
        "--load-script",
        type=Path,
        default=DEFAULT_LOAD_SCRIPT,
        help="Load script path (default: scripts/phase2_load_and_signals.sh).",
    )
    parser.add_argument(
        "--load-label",
        help="Optional LOAD_LABEL override; default is weekly_cycle_<snapshot_date>.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPERATOR_BASE_URL", "http://127.0.0.1:8090"),
        help="Operator app base URL for review links.",
    )
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=DEFAULT_AUDIT_DIR,
        help="Directory for weekly audit JSON files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    started = _utc_now()
    errors: list[str] = []

    # Input/date normalization
    try:
        snapshot_date = _parse_iso_date(args.snapshot_date, "--snapshot-date")
    except argparse.ArgumentTypeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    prior_snapshot_from_arg: Optional[date] = None
    if args.prior_snapshot_date:
        try:
            prior_snapshot_from_arg = _parse_iso_date(args.prior_snapshot_date, "--prior-snapshot-date")
        except argparse.ArgumentTypeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if prior_snapshot_from_arg >= snapshot_date:
            print(
                "ERROR: --prior-snapshot-date must be earlier than --snapshot-date",
                file=sys.stderr,
            )
            return 1

    csv_path = args.csv.resolve()
    if not csv_path.is_file():
        print(f"ERROR: CSV path not found: {csv_path}", file=sys.stderr)
        return 1

    if not args.load_script.exists():
        print(f"ERROR: load script not found: {args.load_script}", file=sys.stderr)
        return 1

    try:
        db_ctx = _resolve_db_context(args)
    except RuntimeError as exc:
        print(f"ERROR: database connection resolution failed: {exc}", file=sys.stderr)
        return 1

    load_status = "SKIPPED"
    refresh_status = "SKIPPED"
    validation_status = "SKIPPED"
    output_urls: dict[str, Optional[str]] = {
        "path_comparison_compare": None,
        "path_comparison_p1_compare": None,
        "path_comparison_current": None,
        "path_comparison_p1_current": None,
        "path_comparison_task_example": None,
        "computed_path_task_example": None,
        "critical_path_task_example": None,
    }
    validation_checks: list[dict[str, Any]] = []

    # Baseline resolution helper
    resolved_prior_snapshot: Optional[date] = prior_snapshot_from_arg

    # Pre-load append-only safety check
    if not args.skip_load:
        pre_count_sql = (
            "SELECT COUNT(*)::text FROM schedule_tasks "
            f"WHERE snapshot_date = {_sql_literal_date(snapshot_date)};"
        )
        pre_count = _run_sql(db_ctx, pre_count_sql)
        if pre_count.exit_code != 0:
            errors.append(f"pre_load_snapshot_check_failed: {(pre_count.stderr or pre_count.stdout).strip()[:600]}")
            load_status = "FAIL"
        else:
            already_loaded = int((pre_count.stdout.strip() or "0").splitlines()[-1])
            if already_loaded > 0:
                errors.append(
                    f"append_only_guard_failed: snapshot_date {snapshot_date.isoformat()} already has {already_loaded} rows"
                )
                load_status = "FAIL"

        if load_status != "FAIL":
            load_env = os.environ.copy()
            load_env["SNAPSHOT_DATE"] = snapshot_date.isoformat()
            load_env["LOAD_LABEL"] = args.load_label or f"weekly_cycle_{snapshot_date.isoformat()}"
            load_env["CSV_LOCAL"] = str(csv_path)
            if args.db_container_for_load:
                load_env["DB_CONTAINER"] = args.db_container_for_load
            elif db_ctx.db_container:
                load_env["DB_CONTAINER"] = db_ctx.db_container

            load_cmd = _run_cmd(["bash", str(args.load_script.resolve())], env=load_env)
            if load_cmd.exit_code != 0:
                load_status = "FAIL"
                errors.append(f"load_failed: {(load_cmd.stderr or load_cmd.stdout).strip()[-1200:]}")
            else:
                load_status = "PASS"

    # Prior snapshot baseline
    if resolved_prior_snapshot is None:
        prior_sql = (
            "SELECT MAX(snapshot_date)::text FROM schedule_tasks "
            f"WHERE snapshot_date < {_sql_literal_date(snapshot_date)};"
        )
        prior_cmd = _run_sql(db_ctx, prior_sql)
        if prior_cmd.exit_code != 0:
            errors.append(f"prior_snapshot_detection_failed: {(prior_cmd.stderr or prior_cmd.stdout).strip()[:600]}")
        else:
            prior_raw = (prior_cmd.stdout.strip() or "").splitlines()
            prior_val = prior_raw[-1].strip() if prior_raw else ""
            if prior_val:
                resolved_prior_snapshot = date.fromisoformat(prior_val)
    if resolved_prior_snapshot is None:
        errors.append(
            "prior_snapshot_detection_failed: no snapshot date exists before "
            f"{snapshot_date.isoformat()}"
        )

    # Refresh
    if not args.skip_refresh and not errors:
        refresh_files = [
            SQL_REFRESH_DEP_GRAPH,
            SQL_REFRESH_COMPUTED,
            SQL_REFRESH_SIGNALS,
        ]
        failed_refresh: Optional[str] = None
        for refresh_file in refresh_files:
            result = _run_sql_file(db_ctx, refresh_file)
            if result.exit_code != 0:
                failed_refresh = (
                    f"{refresh_file.name}: {(result.stderr or result.stdout).strip()[-1200:]}"
                )
                break
        if failed_refresh:
            refresh_status = "FAIL"
            errors.append(f"refresh_failed: {failed_refresh}")
        else:
            refresh_status = "PASS"

    # Validation
    effective_prior = resolved_prior_snapshot
    if not args.skip_validation and not errors:
        # 1) Snapshot presence
        snap_count_cmd = _run_sql(
            db_ctx,
            "SELECT COUNT(*)::text FROM schedule_tasks "
            f"WHERE snapshot_date = {_sql_literal_date(snapshot_date)};",
        )
        if snap_count_cmd.exit_code != 0:
            validation_checks.append(
                {
                    "check_id": "snapshot_rows_present",
                    "status": "ERROR",
                    "detail": (snap_count_cmd.stderr or snap_count_cmd.stdout).strip()[-800:],
                }
            )
        else:
            count_val = int((snap_count_cmd.stdout.strip() or "0").splitlines()[-1])
            validation_checks.append(
                {
                    "check_id": "snapshot_rows_present",
                    "status": "PASS" if count_val > 0 else "FAIL",
                    "detail": {"snapshot_row_count": count_val},
                }
            )

        # 2) Snapshot pair view alignment
        pair_cmd = _run_sql(
            db_ctx,
            "SELECT current_snapshot_date::text, COALESCE(prior_snapshot_date::text, '') "
            "FROM v_schedule_snapshot_pair_latest LIMIT 1;",
        )
        pair_current: Optional[str] = None
        pair_prior: Optional[str] = None
        if pair_cmd.exit_code != 0:
            validation_checks.append(
                {
                    "check_id": "snapshot_pair_alignment",
                    "status": "ERROR",
                    "detail": (pair_cmd.stderr or pair_cmd.stdout).strip()[-800:],
                }
            )
        else:
            lines = [ln for ln in pair_cmd.stdout.splitlines() if ln.strip()]
            if lines:
                parts = lines[-1].split("|", 1)
                pair_current = parts[0].strip() if parts else None
                pair_prior = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
            expect_prior = effective_prior.isoformat() if effective_prior else None
            pair_ok = pair_current == snapshot_date.isoformat() and (expect_prior is None or pair_prior == expect_prior)
            validation_checks.append(
                {
                    "check_id": "snapshot_pair_alignment",
                    "status": "PASS" if pair_ok else "FAIL",
                    "detail": {
                        "expected_current": snapshot_date.isoformat(),
                        "expected_prior": expect_prior,
                        "pair_current": pair_current,
                        "pair_prior": pair_prior,
                    },
                }
            )

        # 3) Comparison surface row count
        comparison_cmd = _run_sql(
            db_ctx,
            "SELECT COUNT(*)::text FROM v_operator_path_comparison_current;",
        )
        if comparison_cmd.exit_code != 0:
            validation_checks.append(
                {
                    "check_id": "comparison_rows_query",
                    "status": "ERROR",
                    "detail": (comparison_cmd.stderr or comparison_cmd.stdout).strip()[-800:],
                }
            )
        else:
            comp_count = int((comparison_cmd.stdout.strip() or "0").splitlines()[-1])
            validation_checks.append(
                {
                    "check_id": "comparison_rows_query",
                    "status": "PASS",
                    "detail": {"comparison_row_count": comp_count},
                }
            )

        # 4) P1 triage count query
        p1_cmd = _run_sql(
            db_ctx,
            "SELECT COUNT(*)::text FROM v_operator_path_comparison_current "
            "WHERE operator_priority_band = 'P1';",
        )
        if p1_cmd.exit_code != 0:
            validation_checks.append(
                {
                    "check_id": "p1_triage_rows_query",
                    "status": "ERROR",
                    "detail": (p1_cmd.stderr or p1_cmd.stdout).strip()[-800:],
                }
            )
        else:
            p1_count = int((p1_cmd.stdout.strip() or "0").splitlines()[-1])
            validation_checks.append(
                {
                    "check_id": "p1_triage_rows_query",
                    "status": "PASS",
                    "detail": {"p1_row_count": p1_count},
                }
            )

        validation_status = (
            "PASS"
            if all(chk.get("status") == "PASS" for chk in validation_checks)
            else "FAIL"
        )

    # Output URLs + optional task examples
    base_url = args.base_url.rstrip("/")
    output_urls["path_comparison_current"] = f"{base_url}/path-comparison"
    output_urls["path_comparison_p1_current"] = f"{base_url}/path-comparison?priority=P1"
    if effective_prior:
        prior_q = effective_prior.isoformat()
        current_q = snapshot_date.isoformat()
        output_urls["path_comparison_compare"] = (
            f"{base_url}/path-comparison?compare_from_snapshot={prior_q}&compare_to_snapshot={current_q}"
        )
        output_urls["path_comparison_p1_compare"] = (
            f"{base_url}/path-comparison?priority=P1&compare_from_snapshot={prior_q}&compare_to_snapshot={current_q}"
        )

    if not errors:
        sample_task_cmd = _run_sql(
            db_ctx,
            "SELECT task_id FROM v_operator_path_comparison_current "
            "WHERE operator_priority_band = 'P1' "
            "ORDER BY classification_rank ASC, task_id ASC LIMIT 1;",
        )
        if sample_task_cmd.exit_code == 0:
            lines = [ln.strip() for ln in sample_task_cmd.stdout.splitlines() if ln.strip()]
            if lines:
                task_id = lines[-1]
                output_urls["path_comparison_task_example"] = f"{base_url}/path-comparison?task_id={task_id}"
                output_urls["computed_path_task_example"] = f"{base_url}/computed-path?task_id={task_id}"
                output_urls["critical_path_task_example"] = f"{base_url}/critical-path?task_id={task_id}"

    overall_status = "PASS"
    if errors:
        overall_status = "FAIL"
    elif validation_status == "FAIL":
        overall_status = "FAIL"
    elif load_status == "FAIL" or refresh_status == "FAIL":
        overall_status = "FAIL"

    # Required audit fields + additive detail
    finished = _utc_now()
    audit_doc: dict[str, Any] = {
        "run_started_at": started.isoformat(),
        "run_finished_at": finished.isoformat(),
        "overall_status": overall_status,
        "snapshot_date": snapshot_date.isoformat(),
        "prior_snapshot_date": effective_prior.isoformat() if effective_prior else None,
        "csv_path": str(csv_path),
        "load_status": load_status,
        "refresh_status": refresh_status,
        "validation_status": validation_status,
        "output_urls": output_urls,
        "error_messages": errors,
        "inputs": {
            "skip_load": args.skip_load,
            "skip_refresh": args.skip_refresh,
            "skip_validation": args.skip_validation,
            "database_url_set": bool(args.database_url),
            "db_container": args.db_container,
            "db_user": args.db_user,
            "db_name": args.db_name,
        },
        "db_resolution": db_ctx.resolution,
        "validation_checks": validation_checks,
    }

    args.audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = args.audit_dir / f"operator_run_weekly_cycle_{_audit_stamp(started)}.json"
    try:
        audit_path.write_text(json.dumps(_as_jsonable(audit_doc), indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: audit write failed: {exc}", file=sys.stderr)
        return 1
    try:
        emit_operator_envelope_weekly_surface(
            repo_root=REPO_ROOT,
            audit_doc=audit_doc,
            audit_json_path=audit_path,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: cannot write operator envelope surface: {exc}", file=sys.stderr)
        return 1

    print(f"OVERALL_STATUS: {overall_status}")
    print(f"snapshot_date: {snapshot_date.isoformat()}")
    print(f"prior_snapshot_date: {effective_prior.isoformat() if effective_prior else 'None'}")
    print(f"load_status: {load_status}")
    print(f"refresh_status: {refresh_status}")
    print(f"validation_status: {validation_status}")
    print("Review URLs:")
    for key in (
        "path_comparison_compare",
        "path_comparison_p1_compare",
        "path_comparison_current",
        "path_comparison_p1_current",
        "path_comparison_task_example",
        "computed_path_task_example",
        "critical_path_task_example",
    ):
        value = output_urls.get(key)
        if value:
            print(f"- {key}: {value}")
    print(f"Audit written: {audit_path}")

    if overall_status != "PASS":
        if errors:
            print("Errors:", file=sys.stderr)
            for msg in errors:
                print(f"- {msg}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
