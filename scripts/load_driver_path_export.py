#!/usr/bin/env python3
"""
Load an engine-authoritative driver-path CSV into schedule_driver_path_staging,
run sql/05_insert_driver_path.sql promotion into schedule_driver_path, and emit PASS/FAIL.

Truth rules: path_sequence and membership come only from the export file; no graph logic.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
PROMOTE_SQL = REPO_ROOT / "sql" / "05_insert_driver_path.sql"

REQUIRED_HEADERS = frozenset(
    {
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
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj


def sql_single_quoted_literal(value: str) -> str:
    """Body only; caller wraps in single quotes for SQL text literals."""
    return value.replace("'", "''")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def run_psql_script(
    *,
    sql_text: str,
    database_url: Optional[str],
    db_container: Optional[str],
    db_user: str,
    db_name: str,
    verbose: bool,
) -> tuple[int, str, str]:
    psql_bin = shutil.which("psql")
    if database_url:
        if not psql_bin:
            return 127, "", "psql not found in PATH (required for --database-url)"
        cmd = [
            psql_bin,
            database_url,
            "-v",
            "ON_ERROR_STOP=1",
            "-1",
            "-f",
            "-",
        ]
        if verbose:
            print("[driver-path] psql -1 -f - (URI)", file=sys.stderr)
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            text=True,
            input=sql_text,
            capture_output=True,
        )
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
        "-1",
        "-f",
        "-",
    ]
    if verbose:
        print(f"[driver-path] docker exec -i {db_container} psql -1 -f -", file=sys.stderr)
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        text=True,
        input=sql_text,
        capture_output=True,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def validate_csv_headers(path: Path) -> tuple[bool, list[str], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return False, [], ["CSV is empty"]
    fields = [h.strip() for h in header]
    missing = sorted(REQUIRED_HEADERS.difference(fields))
    ok = not missing
    detail = []
    if missing:
        detail.append(f"Missing required columns: {', '.join(missing)}")
    return ok, fields, detail


def build_promotion_sql(
    *,
    snapshot_date: str,
    load_label: str,
    source_filename: str,
    source_sha256: str,
) -> str:
    raw = PROMOTE_SQL.read_text(encoding="utf-8")
    out = raw.replace("__BRA_SNAPSHOT__", snapshot_date)
    out = out.replace("__BRA_LOAD__", sql_single_quoted_literal(load_label))
    out = out.replace("__BRA_SOURCE_FILENAME__", sql_single_quoted_literal(source_filename))
    out = out.replace("__BRA_SOURCE_SHA256__", sql_single_quoted_literal(source_sha256))
    return out


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Load authoritative driver-path CSV → staging → schedule_driver_path (Postgres truth)."
    )
    p.add_argument("--csv-path", type=Path, required=True, help="UTF-8 CSV with header row (contract §8).")
    p.add_argument(
        "--snapshot-date",
        required=True,
        metavar="YYYY-MM-DD",
        help="Must match schedule_tasks snapshot_date and CSV snapshot_date column.",
    )
    p.add_argument(
        "--load-label",
        required=True,
        help="Audit label stored on promoted rows (mirrors schedule_tasks.load_label pattern).",
    )
    p.add_argument(
        "--database-url",
        "--db-url",
        dest="database_url",
        metavar="URL",
        help="Postgres URI; precedence over Docker (OPERATOR_DATABASE_URL / DATABASE_URL).",
    )
    p.add_argument(
        "--db-container",
        "--postgres-container",
        dest="db_container",
        metavar="NAME",
        help="Postgres Docker container name when no database URL is set.",
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
    p.add_argument(
        "--audit-json",
        type=Path,
        help="Optional path to write JSON audit record.",
    )
    p.add_argument("--verbose", action="store_true", help="Progress on stderr.")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    csv_path: Path = args.csv_path.resolve()
    if not csv_path.is_file():
        print("FAIL: csv path is not a file", file=sys.stderr)
        return 1

    snap = args.snapshot_date.strip()
    if len(snap) != 10 or snap[4] != "-" or snap[7] != "-":
        print("FAIL: --snapshot-date must be YYYY-MM-DD", file=sys.stderr)
        return 1

    ok_hdr, fields, hdr_detail = validate_csv_headers(csv_path)
    if not ok_hdr:
        print("FAIL: " + "; ".join(hdr_detail), file=sys.stderr)
        return 1

    db_url, db_url_note = resolve_database_url(args.database_url)
    container = args.db_container
    disc_note = ""
    if not db_url:
        if not container:
            container, disc_note = discover_postgres_container()
        if not container:
            print(
                "FAIL: set --database-url / OPERATOR_DATABASE_URL, or run Postgres and pass --db-container",
                file=sys.stderr,
            )
            if disc_note:
                print(f"      ({disc_note})", file=sys.stderr)
            return 1

    sha = sha256_file(csv_path)
    filename = csv_path.name
    load_label = args.load_label

    audit: dict[str, Any] = {
        "kind": "driver_path_ingest",
        "started_at_utc": _utc_now().isoformat(),
        "csv_path": str(csv_path),
        "snapshot_date": snap,
        "load_label": load_label,
        "source_filename": filename,
        "source_file_sha256": sha,
        "csv_headers": fields,
        "database_url_source": db_url_note if db_url else "docker_exec",
        "db_container": container,
    }

    if args.verbose:
        print(f"[driver-path] headers OK ({len(fields)} columns)", file=sys.stderr)
        print(f"[driver-path] sha256={sha}", file=sys.stderr)

    staging_allow = {
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
    }
    csv_echo_only = {"load_label"}
    unknown_headers = [f for f in fields if f not in staging_allow and f not in csv_echo_only]
    if unknown_headers:
        print(
            "FAIL: CSV contains unknown columns (positional COPY requires only contract columns): "
            + ", ".join(unknown_headers),
            file=sys.stderr,
        )
        audit["status"] = "FAIL"
        audit["failure"] = "csv_unknown_columns"
        audit["unknown_headers"] = unknown_headers
        if args.audit_json:
            args.audit_json.write_text(json.dumps(_json_safe(audit), indent=2), encoding="utf-8")
        return 1

    copy_fields = [f for f in fields if f in staging_allow and f != "load_label"]
    if not REQUIRED_HEADERS.issubset(set(copy_fields)):
        missing = sorted(REQUIRED_HEADERS.difference(copy_fields))
        print("FAIL: CSV header row missing columns required for COPY: " + ", ".join(missing), file=sys.stderr)
        audit["status"] = "FAIL"
        audit["failure"] = "csv_header_copy_mismatch"
        if args.audit_json:
            args.audit_json.write_text(json.dumps(_json_safe(audit), indent=2), encoding="utf-8")
        return 1

    col_list = ", ".join(copy_fields)
    audit["staging_copy_columns"] = copy_fields

    truncate_sql = "TRUNCATE TABLE schedule_driver_path_staging;\n"

    if db_url:
        csv_sql_path = str(csv_path).replace("'", "''")
        copy_fragment = (
            f"\\copy schedule_driver_path_staging ({col_list}) FROM '{csv_sql_path}' "
            + "WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');\n"
        )
    else:
        assert container is not None
        docker_bin = shutil.which("docker")
        assert docker_bin
        in_container = f"/tmp/driver_path_{filename.replace('/', '_')}"
        cp = subprocess.run(
            [docker_bin, "cp", str(csv_path), f"{container}:{in_container}"],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
        )
        if cp.returncode != 0:
            print("FAIL: docker cp to container failed", file=sys.stderr)
            print((cp.stderr or cp.stdout or "").strip(), file=sys.stderr)
            audit["status"] = "FAIL"
            audit["failure"] = "docker_cp"
            audit["docker_cp"] = {"exit_code": cp.returncode, "stderr": cp.stderr, "stdout": cp.stdout}
            if args.audit_json:
                args.audit_json.write_text(json.dumps(_json_safe(audit), indent=2), encoding="utf-8")
            return 1
        copy_fragment = (
            f"\\copy schedule_driver_path_staging ({col_list}) FROM '{in_container}' "
            + "WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');\n"
        )

    update_label = (
        "UPDATE schedule_driver_path_staging "
        f"SET load_label = '{sql_single_quoted_literal(load_label)}';\n"
    )

    promote_sql = build_promotion_sql(
        snapshot_date=snap,
        load_label=load_label,
        source_filename=filename,
        source_sha256=sha,
    )

    full_sql = truncate_sql + copy_fragment + update_label + promote_sql

    rc_p, out_p, err_p = run_psql_script(
        sql_text=full_sql,
        database_url=db_url,
        db_container=container,
        db_user=args.db_user,
        db_name=args.db_name,
        verbose=args.verbose,
    )
    audit["ingest_transaction"] = {"exit_code": rc_p, "stdout_tail": (out_p or "")[-2000:], "stderr_tail": (err_p or "")[-8000:]}
    audit["finished_at_utc"] = _utc_now().isoformat()

    if rc_p != 0:
        print("FAIL: driver-path ingest transaction failed (staging and/or promotion rolled back)", file=sys.stderr)
        print((err_p or out_p or "").strip()[-8000:], file=sys.stderr)
        audit["status"] = "FAIL"
        if args.audit_json:
            args.audit_json.write_text(json.dumps(_json_safe(audit), indent=2), encoding="utf-8")
        return 1

    audit["status"] = "PASS"
    if args.audit_json:
        args.audit_json.write_text(json.dumps(_json_safe(audit), indent=2), encoding="utf-8")

    print("PASS: driver-path rows promoted to schedule_driver_path")
    if args.verbose:
        print((out_p or "").strip()[-2000:], file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
