#!/usr/bin/env python3
"""
Read-only first-load guard for driver-path ingestion.

Pre phase:
- verify schedule snapshot exists in schedule_tasks
- verify driver-path CSV headers satisfy contract/loader allowlist

Post phase:
- verify inventory rows exist for snapshot
- verify per-run sequence bounds are contiguous (min=1 and max=row_count)
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED_HEADERS = {
    "path_sequence",
    "task_id",
    "snapshot_date",
    "path_scope",
    "start_date",
    "finish_date",
    "total_float",
    "critical",
    "run_id",
}

STAGING_ALLOW = {
    "path_sequence",
    "task_id",
    "task_name",
    "snapshot_date",
    "path_scope",
    "start_date",
    "finish_date",
    "total_float",
    "critical",
    "path_source",
    "run_id",
    "export_timestamp_utc",
    "tool_name",
    "tool_version",
    "project_id",
    "source_filename",
    "source_file_sha256",
    "load_label",
}


def resolve_database_url(cli_url: Optional[str]) -> Optional[str]:
    if cli_url and cli_url.strip():
        return cli_url.strip()
    for key in ("OPERATOR_DATABASE_URL", "DATABASE_URL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def discover_postgres_container(preferred: str = "bratek-phase1-postgres") -> Optional[str]:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return None
    proc = subprocess.run(
        [docker_bin, "ps", "--format", "{{.Names}}"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    names = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    if preferred in names:
        return preferred
    suffix = "_" + preferred
    matches = [name for name in names if name.endswith(suffix) or name == preferred]
    if len(matches) == 1:
        return matches[0]
    return None


def run_psql(
    sql: str,
    *,
    database_url: Optional[str],
    db_container: Optional[str],
    db_user: str,
    db_name: str,
    tuples_only: bool = False,
) -> tuple[int, str, str]:
    psql_bin = shutil.which("psql")
    args_extra = ["-At"] if tuples_only else []
    if database_url:
        if not psql_bin:
            return 127, "", "psql not found in PATH (required for --database-url)"
        cmd = [psql_bin, database_url, "-v", "ON_ERROR_STOP=1", *args_extra, "-c", sql]
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True)
        return proc.returncode, proc.stdout or "", proc.stderr or ""

    if not db_container:
        return 127, "", "No database_url and no db_container for psql"
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return 127, "", "docker not found in PATH (required for --db-container)"
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
        *args_extra,
        "-c",
        sql,
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def read_headers(csv_path: Path) -> list[str]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        try:
            header = next(reader)
        except StopIteration:
            return []
    return [h.strip() for h in header]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only guard checks for first real driver-path ingestion."
    )
    parser.add_argument(
        "--phase",
        choices=("pre", "post", "both"),
        default="both",
        help="Check phase: pre (before load), post (after load), or both.",
    )
    parser.add_argument(
        "--snapshot-date",
        required=True,
        metavar="YYYY-MM-DD",
        help="Target snapshot date used for schedule and driver-path load.",
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        help="Driver-path CSV path (required for pre or both).",
    )
    parser.add_argument(
        "--database-url",
        "--db-url",
        dest="database_url",
        metavar="URL",
        help="Postgres URI (falls back to OPERATOR_DATABASE_URL / DATABASE_URL).",
    )
    parser.add_argument(
        "--db-container",
        "--postgres-container",
        dest="db_container",
        metavar="NAME",
        help="Postgres Docker container when no database URL is set.",
    )
    parser.add_argument(
        "--db-user",
        default=os.environ.get("OPERATOR_DB_USER", "bratek_ops"),
        help="Postgres user inside container (default: bratek_ops).",
    )
    parser.add_argument(
        "--db-name",
        default=os.environ.get("OPERATOR_DB_NAME", "postgres"),
        help="Database name (default: postgres).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    snapshot_date = args.snapshot_date.strip()
    if not SNAPSHOT_RE.match(snapshot_date):
        print("FAIL: --snapshot-date must be YYYY-MM-DD", file=sys.stderr)
        return 1

    database_url = resolve_database_url(args.database_url)
    db_container = args.db_container or discover_postgres_container()
    if not database_url and not db_container:
        print(
            "FAIL: set --database-url / OPERATOR_DATABASE_URL, or pass --db-container",
            file=sys.stderr,
        )
        return 1

    failed = False
    run_pre = args.phase in ("pre", "both")
    run_post = args.phase in ("post", "both")

    if run_pre:
        if not args.csv_path:
            print("FAIL: --csv-path is required for --phase pre/both")
            return 1
        csv_path = args.csv_path.resolve()
        if not csv_path.is_file():
            print(f"FAIL: csv file not found: {csv_path}")
            return 1

        q_schedule = (
            "SELECT COUNT(*)::bigint FROM schedule_tasks "
            f"WHERE snapshot_date = DATE '{snapshot_date}';"
        )
        rc, out, err = run_psql(
            q_schedule,
            database_url=database_url,
            db_container=db_container,
            db_user=args.db_user,
            db_name=args.db_name,
            tuples_only=True,
        )
        if rc != 0:
            print(f"FAIL: could not query schedule_tasks: {(err or out).strip()}")
            return rc
        schedule_count = int((out or "0").strip() or "0")
        if schedule_count > 0:
            print(f"PASS: schedule_tasks has rows for snapshot_date {snapshot_date} ({schedule_count})")
        else:
            print(f"FAIL: schedule_tasks has no rows for snapshot_date {snapshot_date}")
            failed = True

        headers = read_headers(csv_path)
        if not headers:
            print("FAIL: driver-path CSV has no header row")
            return 1
        missing = sorted(REQUIRED_HEADERS.difference(headers))
        if missing:
            print("FAIL: driver-path CSV missing required columns: " + ", ".join(missing))
            failed = True
        else:
            print("PASS: driver-path CSV contains required contract columns")

        unknown = sorted([h for h in headers if h not in STAGING_ALLOW])
        if unknown:
            print("FAIL: CSV has unknown columns outside loader allowlist: " + ", ".join(unknown))
            failed = True
        else:
            print("PASS: CSV columns are in loader allowlist")

    if run_post:
        q_inventory = f"""
SELECT
  COALESCE(SUM(row_count), 0)::bigint AS total_rows,
  COALESCE(COUNT(*), 0)::bigint AS run_count
FROM v_schedule_driver_path_inventory
WHERE snapshot_date = DATE '{snapshot_date}';
""".strip()
        rc, out, err = run_psql(
            q_inventory,
            database_url=database_url,
            db_container=db_container,
            db_user=args.db_user,
            db_name=args.db_name,
            tuples_only=True,
        )
        if rc != 0:
            print(f"FAIL: could not query v_schedule_driver_path_inventory: {(err or out).strip()}")
            return rc
        rows = [line.strip() for line in (out or "").splitlines() if line.strip()]
        if not rows or "|" not in rows[0]:
            print("FAIL: unexpected inventory query output")
            return 1
        total_rows_str, run_count_str = rows[0].split("|", 1)
        total_rows = int(total_rows_str or "0")
        run_count = int(run_count_str or "0")
        if total_rows > 0 and run_count > 0:
            print(
                f"PASS: inventory has driver-path rows for snapshot_date {snapshot_date} "
                f"(rows={total_rows}, runs={run_count})"
            )
        else:
            print(f"FAIL: inventory has no driver-path rows for snapshot_date {snapshot_date}")
            failed = True

        q_contiguous = f"""
SELECT COUNT(*)::bigint
FROM v_schedule_driver_path_inventory
WHERE snapshot_date = DATE '{snapshot_date}'
  AND (min_path_sequence <> 1 OR max_path_sequence <> row_count);
""".strip()
        rc, out, err = run_psql(
            q_contiguous,
            database_url=database_url,
            db_container=db_container,
            db_user=args.db_user,
            db_name=args.db_name,
            tuples_only=True,
        )
        if rc != 0:
            print(f"FAIL: could not evaluate sequence bounds: {(err or out).strip()}")
            return rc
        bad_runs = int((out or "0").strip() or "0")
        if bad_runs == 0:
            print("PASS: every run has contiguous sequence bounds (min=1 and max=row_count)")
        else:
            print(f"FAIL: {bad_runs} run(s) have non-contiguous sequence bounds")
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
