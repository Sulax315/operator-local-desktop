#!/usr/bin/env python3
"""
Load earned value (EVM) definitions into Postgres: project, baseline curvepoints, and progress snapshots. Uses docker exec or psql DATABASE_URL.
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


def run_sql(
    sql: str,
    *,
    database_url: Optional[str],
    db_container: Optional[str],
    db_user: str,
    db_name: str,
) -> tuple[int, str, str]:
    psql_bin = shutil.which("psql")
    if database_url:
        if not psql_bin:
            return 127, "", "psql not in PATH"
        proc = subprocess.run(
            [psql_bin, database_url, "-v", "ON_ERROR_STOP=1", "-c", sql],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""

    if not db_container:
        return 127, "", "no database URL and no db container"
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return 127, "", "docker not in PATH"
    proc = subprocess.run(
        [
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
            "-c",
            sql,
        ],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def sql_escape_literal(val: str) -> str:
    return val.replace("'", "''")


def sql_numeric_token(val: str) -> str:
    s = val.strip().replace(",", "")
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        raise ValueError(f"invalid numeric token: {val!r}")
    return s


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load EVM project / baseline / snapshots.")
    p.add_argument("--database-url", "--db-url", dest="database_url")
    p.add_argument(
        "--db-container",
        default=os.environ.get("FINANCIAL_DB_CONTAINER", "bratek-phase1-postgres"),
    )
    p.add_argument("--db-user", default=os.environ.get("FINANCIAL_DB_USER", "bratek_ops"))
    p.add_argument("--db-name", default=os.environ.get("FINANCIAL_DB_NAME", "postgres"))

    sub = p.add_subparsers(dest="command", required=True)

    u = sub.add_parser("upsert-project", help="Create or update evm_project.")
    u.add_argument("--code", required=True)
    u.add_argument("--name", default="")
    u.add_argument("--bac", type=float, required=True)
    u.add_argument("--start", dest="start_date", required=True, help="YYYY-MM-DD")
    u.add_argument("--end", dest="end_date", required=True, help="YYYY-MM-DD")

    b = sub.add_parser("load-baseline-csv", help="Load cumulative PV curve from CSV.")
    b.add_argument("--code", required=True)
    b.add_argument(
        "csv_path",
        type=Path,
        help="Header row: point_date,cumulative_pv (ISO dates)",
    )

    s = sub.add_parser("snapshot", help="Insert or update a progress snapshot.")
    s.add_argument("--code", required=True)
    s.add_argument("--date", dest="as_of_date", required=True, help="YYYY-MM-DD")
    s.add_argument(
        "--pct-complete",
        type=float,
        required=True,
        help="Physical percent complete in 0–100 or 0–1 (auto-detected if > 1).",
    )
    s.add_argument("--ac-override", type=float, default=None)
    s.add_argument("--notes", default="")

    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    db_url = (args.database_url or os.environ.get("DATABASE_URL") or "").strip() or None
    container = None if db_url else args.db_container

    if args.command == "upsert-project":
        name = sql_escape_literal((args.name or "").strip())
        code = sql_escape_literal(args.code.strip())
        sql = (
            "INSERT INTO evm_project (project_code, display_name, bac, project_start_date, project_end_date) "
            f"VALUES ('{code}', NULLIF('{name}', '')::text, {args.bac!r}::numeric, "
            f"'{args.start_date}'::date, '{args.end_date}'::date) "
            "ON CONFLICT (project_code) DO UPDATE SET "
            "display_name = EXCLUDED.display_name, "
            "bac = EXCLUDED.bac, "
            "project_start_date = EXCLUDED.project_start_date, "
            "project_end_date = EXCLUDED.project_end_date, "
            "updated_at = now();"
        )
        rc, out, err = run_sql(sql, database_url=db_url, db_container=container, db_user=args.db_user, db_name=args.db_name)
        if rc != 0:
            print(err or out, file=sys.stderr)
            return rc
        print("OK: upsert-project", args.code)
        return 0

    if args.command == "load-baseline-csv":
        path: Path = args.csv_path
        if not path.is_file():
            print(f"ERROR: missing file {path}", file=sys.stderr)
            return 1
        code = sql_escape_literal(args.code.strip())
        delete_sql = f"DELETE FROM evm_baseline_curve_point WHERE project_code = '{code}';"
        rc, out, err = run_sql(delete_sql, database_url=db_url, db_container=container, db_user=args.db_user, db_name=args.db_name)
        if rc != 0:
            print(err or out, file=sys.stderr)
            return rc
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or "point_date" not in reader.fieldnames or "cumulative_pv" not in reader.fieldnames:
                print("ERROR: CSV must have columns point_date,cumulative_pv", file=sys.stderr)
                return 1
            for row in reader:
                pd = (row.get("point_date") or "").strip()
                pv_raw = (row.get("cumulative_pv") or "").strip()
                if not pd or not pv_raw:
                    continue
                try:
                    pv = sql_numeric_token(pv_raw)
                except ValueError as exc:
                    print(f"ERROR: row {row!r}: {exc}", file=sys.stderr)
                    return 1
                ins = (
                    "INSERT INTO evm_baseline_curve_point (project_code, point_date, cumulative_pv) "
                    f"VALUES ('{code}', '{sql_escape_literal(pd)}'::date, {pv}::numeric);"
                )
                rc, out, err = run_sql(ins, database_url=db_url, db_container=container, db_user=args.db_user, db_name=args.db_name)
                if rc != 0:
                    print(err or out, file=sys.stderr)
                    return rc
        print("OK: load-baseline-csv", args.code, str(path))
        return 0

    if args.command == "snapshot":
        pct = float(args.pct_complete)
        if pct > 1.0:
            pct = pct / 100.0
        if pct < 0 or pct > 1:
            print("ERROR: pct-complete must be between 0 and 1 (or 0–100).", file=sys.stderr)
            return 1
        code = sql_escape_literal(args.code.strip())
        notes = sql_escape_literal((args.notes or "").strip())
        ac = "NULL::numeric" if args.ac_override is None else repr(float(args.ac_override)) + "::numeric"
        sql = (
            "INSERT INTO evm_progress_snapshot (project_code, as_of_date, pct_complete, ac_actual_cost_override, notes) "
            f"VALUES ('{code}', '{args.as_of_date}'::date, {pct!r}::numeric, {ac}, NULLIF('{notes}', '')::text) "
            "ON CONFLICT (project_code, as_of_date) DO UPDATE SET "
            "pct_complete = EXCLUDED.pct_complete, "
            "ac_actual_cost_override = EXCLUDED.ac_actual_cost_override, "
            "notes = EXCLUDED.notes, "
            "loaded_at = now();"
        )
        rc, out, err = run_sql(sql, database_url=db_url, db_container=container, db_user=args.db_user, db_name=args.db_name)
        if rc != 0:
            print(err or out, file=sys.stderr)
            return rc
        print("OK: snapshot", args.code, args.as_of_date)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
