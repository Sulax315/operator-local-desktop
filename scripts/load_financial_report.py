#!/usr/bin/env python3
"""
Load cost/profit financial reports (xlsx/csv) into the financial control-loop schema.

This script supports:
- direct Postgres URI mode via psql, or
- docker exec mode against a running Postgres container.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Optional

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_SCHEMA = REPO_ROOT / "sql" / "financial" / "10_financial_control_loop_schema.sql"
SQL_VIEWS = REPO_ROOT / "sql" / "financial" / "11_financial_control_loop_views.sql"
SQL_CHANGE_ORDER_VIEWS = REPO_ROOT / "sql" / "financial" / "13_financial_change_order_views.sql"
SQL_MITIGATION_VIEW = REPO_ROOT / "sql" / "financial" / "12_financial_mitigation_priority_view.sql"
SQL_OPERATOR_HEALTH = REPO_ROOT / "sql" / "financial" / "14_financial_operator_health.sql"
SQL_EVM_SCHEMA = REPO_ROOT / "sql" / "financial" / "15_evm_schema.sql"
SQL_EVM_VIEWS = REPO_ROOT / "sql" / "financial" / "16_evm_views.sql"


COST_FIELD_ALIASES: dict[str, list[str]] = {
    "cost_code": ["cost code", "cost_code", "costcode", "code"],
    "cost_code_name": ["cost code name", "cost_code_name", "costcode_name", "description"],
    "cost_category": ["cost category", "cost_category", "category"],
    "original_budget": ["original budget", "original_budget"],
    "current_budget": ["current budget", "current_budget"],
    "update_current_budget": [
        "update current budget",
        "updated current budget",
        "update_current_budget",
    ],
    "spent_to_date": ["spent to date", "spent_to_date", "actual cost to date"],
    "committed_to_date": ["committed to date", "committed_to_date"],
    "open_commitments": ["open commitments", "open_commitments"],
    "budget_less_committed": ["budget less committed", "budget_less_committed"],
}

PROFIT_FIELD_ALIASES: dict[str, list[str]] = {
    "report_no": ["report no", "report_no", "report number", "report_number"],
    "report_month": ["report month", "report_month", "month"],
    "report_year": ["report year", "report_year", "year"],
    "month_year": ["month year", "month_year", "month-year", "period"],
    "projected_profit": ["projected profit", "projected_profit", "profit projection"],
    "mom_change_pct": ["mom change pct", "mom change %", "mom_change_pct", "mom %"],
    "mom_change_dollars": [
        "mom change dollars",
        "mom change $",
        "mom_change_dollars",
        "mom $",
    ],
}

REQUIRED_COST_FIELDS = ("cost_code", "current_budget", "spent_to_date", "committed_to_date")
REQUIRED_PROFIT_FIELDS = ("projected_profit",)


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
    batch_id: str = ""
    project_code: str = ""
    report_type: str = ""
    report_date: str = ""
    source_file: str = ""
    source_sheet: str = ""
    row_count_loaded: int = 0
    transport: str = ""
    db_container: Optional[str] = None
    steps: list[StepResult] = field(default_factory=list)

    def as_json(self) -> str:
        return json.dumps(
            {
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "batch_id": self.batch_id,
                "project_code": self.project_code,
                "report_type": self.report_type,
                "report_date": self.report_date,
                "source_file": self.source_file,
                "source_sheet": self.source_sheet,
                "row_count_loaded": self.row_count_loaded,
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


def _norm_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(name).strip().lower()).strip()


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load a cost or profit financial report into Postgres.")
    p.add_argument("--report-type", choices=("cost", "profit"), required=True)
    p.add_argument("--file-path", type=Path, required=True, help="Path to xlsx/csv report file.")
    p.add_argument("--project-code", required=True, help="Project code identifier (e.g. 219128).")
    p.add_argument("--report-date", required=True, metavar="YYYY-MM-DD")
    p.add_argument("--sheet", help="Optional sheet name for xlsx files.")
    p.add_argument("--load-label", help="Optional audit label. Defaults to generated value.")
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
        "--skip-ddl",
        action="store_true",
        help="Skip schema/view SQL apply steps (for repeat loads).",
    )
    p.add_argument("--verbose", action="store_true")
    p.add_argument(
        "--operator-actor",
        help="Optional id stored on financial_import_batch.operator_actor (requires schema 14 applied).",
    )
    p.add_argument(
        "--operator-notes",
        help="Optional note stored on financial_import_batch.operator_notes.",
    )
    return p.parse_args(argv)


def resolve_database_url(cli_url: Optional[str]) -> Optional[str]:
    if cli_url and cli_url.strip():
        return cli_url.strip()
    for key in ("OPERATOR_DATABASE_URL", "DATABASE_URL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def resolve_report_file_path(raw_path: Path) -> Path:
    """
    Resolve Windows-style paths when running on Linux/WSL.
    """
    raw = str(raw_path)
    if raw_path.exists():
        return raw_path

    # Match windows drive style path, e.g. C:\Users\...
    if not re.match(r"^[A-Za-z]:[\\/]", raw):
        return raw_path

    win_path = PureWindowsPath(raw)
    drive = (win_path.drive or "").rstrip(":").lower()
    tail_parts = list(win_path.parts[1:])
    tail = "/".join(tail_parts)
    candidates = [
        Path(f"/mnt/{drive}/{tail}"),
        Path(f"/{drive}/{tail}"),
        Path(f"/run/desktop/mnt/host/{drive}/{tail}"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return raw_path


def run_sql_via_psql_uri(sql_text: str, database_url: str) -> tuple[int, str, str]:
    psql_bin = shutil.which("psql")
    if not psql_bin:
        return 127, "", "psql not found in PATH"
    proc = subprocess.run(
        [psql_bin, database_url, "-v", "ON_ERROR_STOP=1", "-1", "-f", "-"],
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
) -> tuple[int, str, str]:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return 127, "", "docker not found in PATH"
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
            "-1",
            "-f",
            "-",
        ],
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
) -> tuple[int, str, str]:
    if database_url:
        return run_sql_via_psql_uri(sql_text, database_url)
    return run_sql_via_docker(sql_text, db_container=db_container, db_user=db_user, db_name=db_name)


def execute_step(
    summary: RunSummary,
    *,
    name: str,
    sql_text: str,
    database_url: Optional[str],
    db_container: str,
    db_user: str,
    db_name: str,
) -> bool:
    rc, out, err = run_sql(
        sql_text,
        database_url=database_url,
        db_container=db_container,
        db_user=db_user,
        db_name=db_name,
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


def load_dataframe(file_path: Path, sheet: Optional[str]) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        kwargs = {"dtype": str}
        if sheet:
            kwargs["sheet_name"] = sheet
        return pd.read_excel(file_path, **kwargs)  # type: ignore[arg-type]
    if suffix == ".csv":
        return pd.read_csv(file_path, dtype=str, encoding="utf-8-sig")
    raise ValueError(f"Unsupported file extension: {suffix}")


def find_column_mapping(df: pd.DataFrame, aliases: dict[str, list[str]]) -> dict[str, str]:
    norm_to_original = {_norm_col(c): str(c) for c in df.columns}
    out: dict[str, str] = {}
    for target, candidate_aliases in aliases.items():
        for alias in candidate_aliases:
            original = norm_to_original.get(_norm_col(alias))
            if original:
                out[target] = original
                break
    return out


def normalized_rows(df: pd.DataFrame, report_type: str) -> pd.DataFrame:
    aliases = COST_FIELD_ALIASES if report_type == "cost" else PROFIT_FIELD_ALIASES
    required = REQUIRED_COST_FIELDS if report_type == "cost" else REQUIRED_PROFIT_FIELDS
    mapping = find_column_mapping(df, aliases)
    missing = [field for field in required if field not in mapping]
    if missing:
        raise ValueError(f"Required columns not found for {report_type} report: {', '.join(missing)}")

    target_fields = list(aliases.keys())
    out = pd.DataFrame()
    for field in target_fields:
        src = mapping.get(field)
        out[field] = df[src].astype(str).where(df[src].notna(), "") if src else ""

    out = out.fillna("").astype(str)
    out = out.apply(lambda col: col.str.strip())
    non_blank_mask = (out != "").any(axis=1)
    out = out.loc[non_blank_mask].reset_index(drop=True)
    if out.empty:
        raise ValueError("No data rows found after normalization")
    return out


def build_batch_insert_sql(
    *,
    batch_id: str,
    project_code: str,
    report_type: str,
    report_date: date,
    source_file: str,
    source_sheet: Optional[str],
    load_label: str,
    operator_actor: Optional[str] = None,
    operator_notes: Optional[str] = None,
) -> str:
    source_sheet_sql = "NULL" if not source_sheet else f"'{_sql_lit(source_sheet)}'"
    actor = (operator_actor or "").strip()
    notes = (operator_notes or "").strip()
    actor_sql = "NULL" if not actor else f"'{_sql_lit(actor)}'"
    notes_sql = "NULL" if not notes else f"'{_sql_lit(notes)}'"
    return f"""
INSERT INTO financial_import_batch (
  batch_id,
  project_code,
  report_type,
  report_date,
  source_file,
  source_sheet,
  load_label,
  operator_actor,
  operator_notes
) VALUES (
  '{_sql_lit(batch_id)}'::uuid,
  '{_sql_lit(project_code)}',
  '{_sql_lit(report_type)}',
  '{report_date.isoformat()}'::date,
  '{_sql_lit(source_file)}',
  {source_sheet_sql},
  '{_sql_lit(load_label)}',
  {actor_sql},
  {notes_sql}
);
"""


def build_copy_sql(report_type: str, csv_path: str) -> str:
    escaped = _sql_lit(csv_path)
    if report_type == "cost":
        return (
            "\\copy financial_cost_report_raw ("
            "batch_id, row_number, cost_code, cost_code_name, cost_category, original_budget, current_budget, "
            "update_current_budget, spent_to_date, committed_to_date, open_commitments, budget_less_committed"
            f") FROM '{escaped}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');\n"
        )
    return (
        "\\copy financial_profit_report_raw ("
        "batch_id, row_number, report_no, report_month, report_year, month_year, projected_profit, "
        "mom_change_pct, mom_change_dollars"
        f") FROM '{escaped}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');\n"
    )


def copy_into_container(local_path: Path, db_container: str) -> tuple[int, str, str, str]:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return 127, "", "docker not found in PATH", ""
    remote_path = f"/tmp/{local_path.name}"
    proc = subprocess.run(
        [docker_bin, "cp", str(local_path.resolve()), f"{db_container}:{remote_path}"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or "", remote_path


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    resolved_file_path = resolve_report_file_path(args.file_path)
    if not resolved_file_path.exists():
        print(f"ERROR: file not found: {args.file_path}", file=sys.stderr)
        return 2

    try:
        report_date = date.fromisoformat(args.report_date)
    except ValueError:
        print("ERROR: --report-date must be YYYY-MM-DD", file=sys.stderr)
        return 2

    db_url = resolve_database_url(args.database_url)
    batch_id = str(uuid.uuid4())
    load_label = args.load_label or f"{args.project_code}-{args.report_type}-{report_date.isoformat()}"

    summary = RunSummary(
        started_at=_utc_now(),
        batch_id=batch_id,
        project_code=args.project_code,
        report_type=args.report_type,
        report_date=report_date.isoformat(),
        source_file=str(resolved_file_path.resolve()),
        source_sheet=args.sheet or "",
        transport="psql_uri" if db_url else "docker_exec",
        db_container=None if db_url else args.db_container,
    )

    try:
        raw_df = load_dataframe(resolved_file_path, args.sheet)
        report_df = normalized_rows(raw_df, args.report_type)
    except Exception as exc:
        summary.steps.append(StepResult(name="normalize_input", ok=False, detail=str(exc)))
        summary.finished_at = _utc_now()
        print(summary.as_json())
        return 1

    report_df.insert(0, "row_number", report_df.index + 1)
    report_df.insert(0, "batch_id", batch_id)
    summary.row_count_loaded = int(len(report_df))
    summary.steps.append(
        StepResult(name="normalize_input", ok=True, detail=f"rows={summary.row_count_loaded}")
    )

    with tempfile.TemporaryDirectory(prefix="financial-load-") as tmp_dir:
        tmp_csv = Path(tmp_dir) / f"{args.report_type}_normalized.csv"
        report_df.to_csv(tmp_csv, index=False)

        if not args.skip_ddl:
            if not execute_step(
                summary,
                name="apply_schema",
                sql_text=SQL_SCHEMA.read_text(encoding="utf-8"),
                database_url=db_url,
                db_container=args.db_container,
                db_user=args.db_user,
                db_name=args.db_name,
            ):
                summary.finished_at = _utc_now()
                print(summary.as_json())
                return 1

            if not execute_step(
                summary,
                name="apply_views",
                sql_text=SQL_VIEWS.read_text(encoding="utf-8"),
                database_url=db_url,
                db_container=args.db_container,
                db_user=args.db_user,
                db_name=args.db_name,
            ):
                summary.finished_at = _utc_now()
                print(summary.as_json())
                return 1

            if not execute_step(
                summary,
                name="apply_change_order_views",
                sql_text=SQL_CHANGE_ORDER_VIEWS.read_text(encoding="utf-8"),
                database_url=db_url,
                db_container=args.db_container,
                db_user=args.db_user,
                db_name=args.db_name,
            ):
                summary.finished_at = _utc_now()
                print(summary.as_json())
                return 1

            if not execute_step(
                summary,
                name="apply_mitigation_view",
                sql_text=SQL_MITIGATION_VIEW.read_text(encoding="utf-8"),
                database_url=db_url,
                db_container=args.db_container,
                db_user=args.db_user,
                db_name=args.db_name,
            ):
                summary.finished_at = _utc_now()
                print(summary.as_json())
                return 1

            if not execute_step(
                summary,
                name="apply_operator_health",
                sql_text=SQL_OPERATOR_HEALTH.read_text(encoding="utf-8"),
                database_url=db_url,
                db_container=args.db_container,
                db_user=args.db_user,
                db_name=args.db_name,
            ):
                summary.finished_at = _utc_now()
                print(summary.as_json())
                return 1

            if not execute_step(
                summary,
                name="apply_evm_schema",
                sql_text=SQL_EVM_SCHEMA.read_text(encoding="utf-8"),
                database_url=db_url,
                db_container=args.db_container,
                db_user=args.db_user,
                db_name=args.db_name,
            ):
                summary.finished_at = _utc_now()
                print(summary.as_json())
                return 1

            if not execute_step(
                summary,
                name="apply_evm_views",
                sql_text=SQL_EVM_VIEWS.read_text(encoding="utf-8"),
                database_url=db_url,
                db_container=args.db_container,
                db_user=args.db_user,
                db_name=args.db_name,
            ):
                summary.finished_at = _utc_now()
                print(summary.as_json())
                return 1

        if not execute_step(
            summary,
            name="insert_import_batch",
            sql_text=build_batch_insert_sql(
                batch_id=batch_id,
                project_code=args.project_code,
                report_type=args.report_type,
                report_date=report_date,
                source_file=str(resolved_file_path.resolve()),
                source_sheet=args.sheet,
                load_label=load_label,
                operator_actor=getattr(args, "operator_actor", None),
                operator_notes=getattr(args, "operator_notes", None),
            ),
            database_url=db_url,
            db_container=args.db_container,
            db_user=args.db_user,
            db_name=args.db_name,
        ):
            summary.finished_at = _utc_now()
            print(summary.as_json())
            return 1

        if db_url:
            copy_sql = build_copy_sql(args.report_type, str(tmp_csv.resolve()))
            if not execute_step(
                summary,
                name="copy_rows",
                sql_text=copy_sql,
                database_url=db_url,
                db_container=args.db_container,
                db_user=args.db_user,
                db_name=args.db_name,
            ):
                summary.finished_at = _utc_now()
                print(summary.as_json())
                return 1
        else:
            cp_rc, cp_out, cp_err, remote_csv = copy_into_container(tmp_csv, args.db_container)
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
                name="copy_rows",
                sql_text=build_copy_sql(args.report_type, remote_csv),
                database_url=None,
                db_container=args.db_container,
                db_user=args.db_user,
                db_name=args.db_name,
            ):
                summary.finished_at = _utc_now()
                print(summary.as_json())
                return 1

    summary.finished_at = _utc_now()
    print(summary.as_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
