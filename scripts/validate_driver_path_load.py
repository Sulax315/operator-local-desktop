#!/usr/bin/env python3
"""
Read-only check of ingested driver-path truth in schedule_driver_path.

Prints row counts, sequence bounds, scopes, and sample rows for the target snapshot
(default: latest snapshot_date present in the table).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def resolve_database_url(cli_url: Optional[str]) -> tuple[Optional[str], str]:
    if cli_url and cli_url.strip():
        return cli_url.strip(), "argv --database-url / --db-url"
    for key in ("OPERATOR_DATABASE_URL", "DATABASE_URL"):
        v = os.environ.get(key, "").strip()
        if v:
            return v, f"environment {key}"
    return None, "not_set"


def discover_postgres_container(preferred: str = "bratek-phase1-postgres") -> tuple[Optional[str], str]:
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


def sql_date_literal(ymd: str) -> str:
    if not SNAPSHOT_RE.match(ymd):
        raise ValueError("snapshot_date must be YYYY-MM-DD")
    return ymd


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Read-only summary of schedule_driver_path for operator QA after ingest."
    )
    p.add_argument(
        "--snapshot-date",
        metavar="YYYY-MM-DD",
        help="Restrict to this snapshot_date (default: MAX(snapshot_date) in schedule_driver_path).",
    )
    p.add_argument(
        "--sample-limit",
        type=int,
        default=15,
        metavar="N",
        help="Max sample rows to print (default: 15).",
    )
    p.add_argument(
        "--database-url",
        "--db-url",
        dest="database_url",
        metavar="URL",
        help="Postgres URI (OPERATOR_DATABASE_URL / DATABASE_URL if omitted).",
    )
    p.add_argument(
        "--db-container",
        "--postgres-container",
        dest="db_container",
        metavar="NAME",
        help="Postgres Docker container when no database URL is set.",
    )
    p.add_argument(
        "--db-user",
        default=os.environ.get("OPERATOR_DB_USER", "bratek_ops"),
        help="Postgres user inside container (default: bratek_ops).",
    )
    p.add_argument(
        "--db-name",
        default=os.environ.get("OPERATOR_DB_NAME", "postgres"),
        help="Database name (default: postgres).",
    )
    p.add_argument("--verbose", action="store_true", help="Print transport notes on stderr.")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    db_url, _src = resolve_database_url(args.database_url)
    container = args.db_container
    if not db_url:
        if not container:
            container, note = discover_postgres_container()
            if args.verbose and note:
                print(f"[validate-driver-path] {note}", file=sys.stderr)
        if not container:
            print(
                "FAIL: set --database-url / OPERATOR_DATABASE_URL, or pass --db-container",
                file=sys.stderr,
            )
            return 1

    snap_filter = ""
    if args.snapshot_date:
        sd = sql_date_literal(args.snapshot_date.strip())
        snap_filter = f"WHERE snapshot_date = DATE '{sd}'"
        target_desc = sd
    else:
        rc0, out0, err0 = run_psql(
            "SELECT COALESCE(TO_CHAR(MAX(snapshot_date), 'YYYY-MM-DD'), '') FROM schedule_driver_path;",
            database_url=db_url,
            db_container=container,
            db_user=args.db_user,
            db_name=args.db_name,
            tuples_only=True,
        )
        if rc0 != 0:
            print(err0 or out0, file=sys.stderr)
            return rc0
        raw = (out0 or "").strip().splitlines()
        raw = raw[0].strip() if raw else ""
        if not raw:
            print("schedule_driver_path: (no rows in table)")
            return 0
        sd = sql_date_literal(raw)
        snap_filter = f"WHERE snapshot_date = DATE '{sd}'"
        target_desc = f"{sd} (latest snapshot in table)"

    if args.verbose:
        print(f"[validate-driver-path] target snapshot: {target_desc}", file=sys.stderr)

    q_count = f"""
SELECT COUNT(*)::text AS row_count,
       COALESCE(MIN(path_sequence)::text, '') AS min_seq,
       COALESCE(MAX(path_sequence)::text, '') AS max_seq
FROM schedule_driver_path
{snap_filter};
""".strip()

    q_scopes = f"""
SELECT string_agg(path_scope, ', ' ORDER BY path_scope)
FROM (SELECT DISTINCT path_scope FROM schedule_driver_path {snap_filter}) s;
""".strip()

    lim = max(1, min(args.sample_limit, 500))
    q_sample = f"""
SELECT snapshot_date, path_scope, run_id, path_sequence, task_id,
       left(coalesce(task_name, ''), 40) AS task_name_40,
       start_date, finish_date, total_float_days, critical, coalesce(load_label, '') AS load_label
FROM schedule_driver_path
{snap_filter}
ORDER BY path_scope, run_id, path_sequence
LIMIT {lim};
""".strip()

    rc1, out1, err1 = run_psql(q_count, database_url=db_url, db_container=container, db_user=args.db_user, db_name=args.db_name)
    if rc1 != 0:
        print(err1 or out1, file=sys.stderr)
        return rc1

    rc2, out2, err2 = run_psql(q_scopes, database_url=db_url, db_container=container, db_user=args.db_user, db_name=args.db_name)
    if rc2 != 0:
        print(err2 or out2, file=sys.stderr)
        return rc2

    rc3, out3, err3 = run_psql(q_sample, database_url=db_url, db_container=container, db_user=args.db_user, db_name=args.db_name)
    if rc3 != 0:
        print(err3 or out3, file=sys.stderr)
        return rc3

    print(f"schedule_driver_path — snapshot: {target_desc}")
    print()
    print("— row count / path_sequence bounds —")
    print(out1.rstrip())
    print()
    print("— distinct path_scope (comma-separated) —")
    line = (out2 or "").strip().splitlines()
    print(line[-1] if line else "(none)")
    print()
    print(f"— sample rows (limit {lim}) —")
    print(out3.rstrip())

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
