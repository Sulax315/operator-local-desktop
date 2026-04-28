#!/usr/bin/env python3
"""
Load an ASTA schedule snapshot CSV into schedule_tasks and refresh signal views.

This loader keeps truth logic in SQL/Postgres and supports either:
- direct psql URI mode, or
- docker exec mode against a running Postgres container.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_SCHEMA = REPO_ROOT / "sql" / "01_schema.sql"
SQL_INSERT = REPO_ROOT / "sql" / "03_insert_schedule_tasks.sql"
SQL_DEP_GRAPH = REPO_ROOT / "sql" / "06_refresh_dependency_graph.sql"
SQL_SIGNALS = REPO_ROOT / "sql" / "04_signals.sql"
SQL_WOW_SIGNALS = REPO_ROOT / "sql" / "17_schedule_wow_signals.sql"

REQUIRED_HEADERS = frozenset(
    {
        "Task ID",
        "Task name",
        "Unique task ID",
        "Duration",
        "Duration remaining",
        "Start",
        "Finish",
        "Early start",
        "Early finish",
        "Late start",
        "Late finish",
        "Total float",
        "Free float",
        "Critical",
        "Predecessors",
        "Successors",
        "Critical path drag",
        "Phase Exec",
        "Control Account",
        "Area Zone",
        "Level",
        "CSI",
        "System",
        "Percent complete",
        "Original start",
        "Original finish",
    }
)


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""
    stdout_tail: str = ""
    stderr_tail: str = ""


@dataclass
class RunSummary:
    started_at: str = ""
    finished_at: str = ""
    snapshot_date: str = ""
    load_label: str = ""
    csv_path: str = ""
    row_count_scanned: int = 0
    transport: str = ""
    db_container: Optional[str] = None
    steps: list[StepResult] = field(default_factory=list)

    def as_json(self) -> str:
        return json.dumps(
            {
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "snapshot_date": self.snapshot_date,
                "load_label": self.load_label,
                "csv_path": self.csv_path,
                "row_count_scanned": self.row_count_scanned,
                "transport": self.transport,
                "db_container": self.db_container,
                "steps": [
                    {
                        "name": s.name,
                        "ok": s.ok,
                        "detail": s.detail,
                        "stdout_tail": s.stdout_tail,
                        "stderr_tail": s.stderr_tail,
                    }
                    for s in self.steps
                ],
            },
            indent=2,
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sql_lit(value: str) -> str:
    return value.replace("'", "''")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Load ASTA schedule snapshot CSV and refresh WoW signal views."
    )
    p.add_argument("--csv-path", type=Path, required=True, help="Input ASTA CSV export path.")
    p.add_argument(
        "--snapshot-date",
        required=True,
        metavar="YYYY-MM-DD",
        help="Snapshot date to stamp on imported rows.",
    )
    p.add_argument("--load-label", required=True, help="Audit label written to schedule_tasks.load_label.")
    p.add_argument(
        "--database-url",
        "--db-url",
        dest="database_url",
        help="Postgres URI; precedence over Docker container mode.",
    )
    p.add_argument(
        "--db-container",
        default=os.environ.get("OPERATOR_DB_CONTAINER", "bratek-phase1-postgres"),
        help="Postgres container name for docker exec mode.",
    )
    p.add_argument("--db-user", default=os.environ.get("OPERATOR_DB_USER", "bratek_ops"))
    p.add_argument("--db-name", default=os.environ.get("OPERATOR_DB_NAME", "postgres"))
    p.add_argument(
        "--skip-schema",
        action="store_true",
        help="Skip reapplying sql/01_schema.sql before load.",
    )
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


def resolve_database_url(cli_url: Optional[str]) -> tuple[Optional[str], str]:
    if cli_url and cli_url.strip():
        return cli_url.strip(), "argv --database-url / --db-url"
    for key in ("OPERATOR_DATABASE_URL", "DATABASE_URL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value, f"environment {key}"
    return None, "not_set"


def run_sql_via_psql_uri(sql_text: str, database_url: str, verbose: bool) -> tuple[int, str, str]:
    psql_bin = shutil.which("psql")
    if not psql_bin:
        return 127, "", "psql not found in PATH"
    cmd = [psql_bin, database_url, "-v", "ON_ERROR_STOP=1", "-1", "-f", "-"]
    if verbose:
        print("[loader] psql uri mode", file=sys.stderr)
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        text=True,
        input=sql_text,
        capture_output=True,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def run_sql_via_docker(
    sql_text: str,
    *,
    db_container: str,
    db_user: str,
    db_name: str,
    verbose: bool,
) -> tuple[int, str, str]:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return 127, "", "docker not found in PATH"
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
        "-1",
        "-f",
        "-",
    ]
    if verbose:
        print(f"[loader] docker exec mode container={db_container}", file=sys.stderr)
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        text=True,
        input=sql_text,
        capture_output=True,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def run_sql(
    sql_text: str,
    *,
    database_url: Optional[str],
    db_container: str,
    db_user: str,
    db_name: str,
    verbose: bool,
) -> tuple[int, str, str]:
    if database_url:
        return run_sql_via_psql_uri(sql_text, database_url, verbose)
    return run_sql_via_docker(
        sql_text,
        db_container=db_container,
        db_user=db_user,
        db_name=db_name,
        verbose=verbose,
    )


def validate_csv_headers(path: Path) -> tuple[bool, list[str], list[str], int]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return False, [], ["CSV header row missing"], 0
        headers = [h.strip() for h in reader.fieldnames]
        missing = sorted(REQUIRED_HEADERS.difference(headers))
        row_count = 0
        for row in reader:
            if any((v or "").strip() for v in row.values()):
                row_count += 1
    ok = not missing
    detail = []
    if missing:
        detail.append(f"Missing required columns: {', '.join(missing)}")
    return ok, headers, detail, row_count


def build_insert_sql(snapshot_date: str, load_label: str) -> str:
    raw = SQL_INSERT.read_text(encoding="utf-8")
    out = raw.replace("__BRA_SNAPSHOT__", snapshot_date)
    out = out.replace("__BRA_LOAD__", _sql_lit(load_label))
    return out


def build_staging_load_sql_for_uri(csv_path: Path) -> str:
    escaped = _sql_lit(str(csv_path.resolve()))
    return (
        "TRUNCATE TABLE schedule_import_staging;\n"
        "\\copy schedule_import_staging (task_id, task_name, unique_task_id, duration, duration_remaining, start_date_raw, "
        "finish_date_raw, early_start_raw, early_finish_raw, late_start_raw, late_finish_raw, total_float_raw, free_float_raw, "
        "critical_raw, predecessors, successors, critical_path_drag_raw, phase_exec, control_account, area_zone, level_name, csi, "
        "system_name, percent_complete_raw, original_start_raw, original_finish_raw) "
        f"FROM '{escaped}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');\n"
        "DELETE FROM schedule_import_staging WHERE NULLIF(TRIM(task_id), '') IS NULL;\n"
    )


def copy_csv_into_container(csv_path: Path, db_container: str) -> tuple[int, str, str, str]:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return 127, "", "docker not found in PATH", ""
    in_container = f"/tmp/{csv_path.name}"
    cmd = [docker_bin, "cp", str(csv_path.resolve()), f"{db_container}:{in_container}"]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True)
    return proc.returncode, proc.stdout or "", proc.stderr or "", in_container


def build_staging_load_sql_for_container(csv_in_container: str) -> str:
    escaped = _sql_lit(csv_in_container)
    return (
        "TRUNCATE TABLE schedule_import_staging;\n"
        "\\copy schedule_import_staging (task_id, task_name, unique_task_id, duration, duration_remaining, start_date_raw, "
        "finish_date_raw, early_start_raw, early_finish_raw, late_start_raw, late_finish_raw, total_float_raw, free_float_raw, "
        "critical_raw, predecessors, successors, critical_path_drag_raw, phase_exec, control_account, area_zone, level_name, csi, "
        "system_name, percent_complete_raw, original_start_raw, original_finish_raw) "
        f"FROM '{escaped}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');\n"
        "DELETE FROM schedule_import_staging WHERE NULLIF(TRIM(task_id), '') IS NULL;\n"
    )


def execute_step(
    summary: RunSummary,
    *,
    name: str,
    sql_text: str,
    database_url: Optional[str],
    db_container: str,
    db_user: str,
    db_name: str,
    verbose: bool,
) -> bool:
    rc, out, err = run_sql(
        sql_text,
        database_url=database_url,
        db_container=db_container,
        db_user=db_user,
        db_name=db_name,
        verbose=verbose,
    )
    ok = rc == 0
    summary.steps.append(
        StepResult(
            name=name,
            ok=ok,
            detail="ok" if ok else f"exit_code={rc}",
            stdout_tail=out[-2000:],
            stderr_tail=err[-2000:],
        )
    )
    return ok


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    csv_path = args.csv_path
    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        return 2

    ok, _headers, header_detail, row_count = validate_csv_headers(csv_path)
    if not ok:
        print("ERROR: CSV header validation failed", file=sys.stderr)
        for line in header_detail:
            print(f"  - {line}", file=sys.stderr)
        return 2

    db_url, db_url_resolution = resolve_database_url(args.database_url)
    summary = RunSummary(
        started_at=_utc_now(),
        snapshot_date=args.snapshot_date,
        load_label=args.load_label,
        csv_path=str(csv_path.resolve()),
        row_count_scanned=row_count,
        transport="psql_uri" if db_url else "docker_exec",
        db_container=None if db_url else args.db_container,
    )
    if args.verbose:
        print(f"[loader] db_url_resolution={db_url_resolution}", file=sys.stderr)

    if not args.skip_schema:
        if not execute_step(
            summary,
            name="apply_schema",
            sql_text=SQL_SCHEMA.read_text(encoding="utf-8"),
            database_url=db_url,
            db_container=args.db_container,
            db_user=args.db_user,
            db_name=args.db_name,
            verbose=args.verbose,
        ):
            summary.finished_at = _utc_now()
            print(summary.as_json())
            return 1

    if db_url:
        staging_sql = build_staging_load_sql_for_uri(csv_path)
        if not execute_step(
            summary,
            name="load_staging_from_csv",
            sql_text=staging_sql,
            database_url=db_url,
            db_container=args.db_container,
            db_user=args.db_user,
            db_name=args.db_name,
            verbose=args.verbose,
        ):
            summary.finished_at = _utc_now()
            print(summary.as_json())
            return 1
    else:
        cp_rc, cp_out, cp_err, container_path = copy_csv_into_container(csv_path, args.db_container)
        summary.steps.append(
            StepResult(
                name="copy_csv_to_container",
                ok=cp_rc == 0,
                detail="ok" if cp_rc == 0 else f"exit_code={cp_rc}",
                stdout_tail=cp_out[-2000:],
                stderr_tail=cp_err[-2000:],
            )
        )
        if cp_rc != 0:
            summary.finished_at = _utc_now()
            print(summary.as_json())
            return 1
        if not execute_step(
            summary,
            name="load_staging_from_container_csv",
            sql_text=build_staging_load_sql_for_container(container_path),
            database_url=None,
            db_container=args.db_container,
            db_user=args.db_user,
            db_name=args.db_name,
            verbose=args.verbose,
        ):
            summary.finished_at = _utc_now()
            print(summary.as_json())
            return 1

    if not execute_step(
        summary,
        name="insert_typed_rows",
        sql_text=build_insert_sql(args.snapshot_date, args.load_label),
        database_url=db_url,
        db_container=args.db_container,
        db_user=args.db_user,
        db_name=args.db_name,
        verbose=args.verbose,
    ):
        summary.finished_at = _utc_now()
        print(summary.as_json())
        return 1

    if not execute_step(
        summary,
        name="refresh_dependency_graph",
        sql_text=SQL_DEP_GRAPH.read_text(encoding="utf-8"),
        database_url=db_url,
        db_container=args.db_container,
        db_user=args.db_user,
        db_name=args.db_name,
        verbose=args.verbose,
    ):
        summary.finished_at = _utc_now()
        print(summary.as_json())
        return 1

    if not execute_step(
        summary,
        name="refresh_core_signals",
        sql_text=SQL_SIGNALS.read_text(encoding="utf-8"),
        database_url=db_url,
        db_container=args.db_container,
        db_user=args.db_user,
        db_name=args.db_name,
        verbose=args.verbose,
    ):
        summary.finished_at = _utc_now()
        print(summary.as_json())
        return 1

    if SQL_WOW_SIGNALS.exists():
        if not execute_step(
            summary,
            name="refresh_wow_signals",
            sql_text=SQL_WOW_SIGNALS.read_text(encoding="utf-8"),
            database_url=db_url,
            db_container=args.db_container,
            db_user=args.db_user,
            db_name=args.db_name,
            verbose=args.verbose,
        ):
            summary.finished_at = _utc_now()
            print(summary.as_json())
            return 1
    else:
        summary.steps.append(
            StepResult(
                name="refresh_wow_signals",
                ok=False,
                detail=f"missing SQL file: {SQL_WOW_SIGNALS}",
            )
        )
        summary.finished_at = _utc_now()
        print(summary.as_json())
        return 1

    summary.finished_at = _utc_now()
    print(summary.as_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
