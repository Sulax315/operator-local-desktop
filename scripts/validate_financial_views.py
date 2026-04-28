#!/usr/bin/env python3
"""
Verify financial control-loop views exist and optionally return row counts for a project.
Exit 0 when all checks pass; non-zero on failure. Supports docker exec or psql URI.
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

REQUIRED_VIEWS = (
    "v_financial_exec_kpi_latest",
    "v_financial_profit_trend",
    "v_financial_cost_code_variance_latest",
    "v_financial_exception_alerts_latest",
    "v_financial_cost_line_change_order_class_latest",
    "v_financial_cost_rollup_by_change_order_kind_latest",
    "v_financial_mitigation_priority_latest",
    "v_financial_operator_health",
    "v_financial_data_quality_flags_latest",
    "v_financial_training_signals_latest",
    "v_financial_training_signal_portfolio_latest",
    "v_evm_kpi_latest",
    "v_evm_snapshot_history",
    "v_evm_baseline_curve_ordered",
)


def run_psql_sql(
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
            [psql_bin, database_url, "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
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
            "-At",
            "-c",
            sql,
        ],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate financial Postgres views.")
    p.add_argument(
        "--project-code",
        metavar="CODE",
        help="If set, require at least one cost variance row for this project.",
    )
    p.add_argument("--database-url", "--db-url", dest="database_url", metavar="URL")
    p.add_argument(
        "--db-container",
        default=os.environ.get("FINANCIAL_DB_CONTAINER", os.environ.get("OPERATOR_DB_CONTAINER", "")).strip()
        or "bratek-phase1-postgres",
    )
    p.add_argument("--db-user", default=os.environ.get("FINANCIAL_DB_USER", "bratek_ops"))
    p.add_argument("--db-name", default=os.environ.get("FINANCIAL_DB_NAME", "postgres"))
    p.add_argument("-q", "--quiet", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    db_url = (args.database_url or os.environ.get("OPERATOR_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip() or None

    failed = False
    for view in REQUIRED_VIEWS:
        sql = f"SELECT COUNT(*) FROM {view};"
        rc, out, err = run_psql_sql(
            sql,
            database_url=db_url,
            db_container=None if db_url else args.db_container,
            db_user=args.db_user,
            db_name=args.db_name,
        )
        if rc != 0:
            failed = True
            print(f"FAIL: {view} — exit {rc}\n{err.strip()}", file=sys.stderr)
            continue
        try:
            n = int((out.strip() or "0").splitlines()[-1])
        except ValueError:
            failed = True
            print(f"FAIL: {view} — bad output {out!r}", file=sys.stderr)
            continue
        if not args.quiet:
            print(f"OK: {view} row_count={n}")

    if args.project_code:
        pc = args.project_code.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", pc):
            print("FAIL: --project-code must match [A-Za-z0-9_.-]+", file=sys.stderr)
            return 1
        esc = pc.replace("'", "''")
        sql = (
            "SELECT COUNT(*) FROM v_financial_cost_code_variance_latest "
            f"WHERE project_code = '{esc}';"
        )
        rc, out, err = run_psql_sql(
            sql,
            database_url=db_url,
            db_container=None if db_url else args.db_container,
            db_user=args.db_user,
            db_name=args.db_name,
        )
        if rc != 0:
            failed = True
            print(f"FAIL: project probe — {err}", file=sys.stderr)
        else:
            try:
                n = int((out.strip() or "0").splitlines()[-1])
            except ValueError:
                failed = True
                n = -1
            if n < 1:
                failed = True
                print(
                    f"FAIL: no rows in v_financial_cost_code_variance_latest for project_code={pc!r}",
                    file=sys.stderr,
                )
            elif not args.quiet:
                print(f"OK: project {pc!r} variance lines={n}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
