#!/usr/bin/env python3
"""
Bulk load financial report files from a CSV manifest.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

from load_financial_report import resolve_report_file_path


REPO_ROOT = Path(__file__).resolve().parent.parent
LOADER_SCRIPT = REPO_ROOT / "scripts" / "load_financial_report.py"
REQUIRED_COLUMNS = ("project_code", "report_type", "report_date", "file_path")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load multiple cost/profit reports from a CSV manifest.")
    p.add_argument("--manifest-path", type=Path, required=True)
    p.add_argument("--continue-on-error", action="store_true")
    p.add_argument("--skip-ddl", action="store_true")
    p.add_argument("--db-url", dest="db_url", help="Optional DB URL passed to each load command.")
    p.add_argument("--db-container", help="Optional DB container passed to each load command.")
    p.add_argument("--db-user", help="Optional DB user passed to each load command.")
    p.add_argument("--db-name", help="Optional DB name passed to each load command.")
    p.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate manifest rows and file paths without loading anything.",
    )
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.manifest_path.exists():
        print(f"ERROR: manifest not found: {args.manifest_path}", file=sys.stderr)
        return 2

    with args.manifest_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            print("ERROR: manifest missing header row", file=sys.stderr)
            return 2
        missing_columns = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing_columns:
            print(
                f"ERROR: manifest missing required columns: {', '.join(missing_columns)}",
                file=sys.stderr,
            )
            return 2

        preflight_missing = 0
        preflight_checked = 0
        failures = 0
        for idx, row in enumerate(reader, start=2):
            project_code = (row.get("project_code") or "").strip()
            report_type = (row.get("report_type") or "").strip().lower()
            report_date = (row.get("report_date") or "").strip()
            file_path = (row.get("file_path") or "").strip()
            sheet = (row.get("sheet") or "").strip()
            load_label = (row.get("load_label") or "").strip()

            if not project_code or not report_type or not report_date or not file_path:
                print(f"[manifest] skipping row {idx}: missing required value(s)", file=sys.stderr)
                continue

            preflight_checked += 1
            resolved = resolve_report_file_path(Path(file_path))
            exists = resolved.exists()
            if args.preflight_only:
                status = "OK" if exists else "MISSING"
                resolved_str = str(resolved)
                print(
                    f"[preflight] row={idx} status={status} project={project_code} "
                    f"type={report_type} date={report_date} path=\"{file_path}\" "
                    f"resolved=\"{resolved_str}\""
                )
                if not exists:
                    preflight_missing += 1
                continue

            cmd = [
                sys.executable,
                str(LOADER_SCRIPT),
                "--report-type",
                report_type,
                "--project-code",
                project_code,
                "--report-date",
                report_date,
                "--file-path",
                file_path,
            ]
            if sheet:
                cmd.extend(["--sheet", sheet])
            if load_label:
                cmd.extend(["--load-label", load_label])
            if args.skip_ddl:
                cmd.append("--skip-ddl")
            if args.db_url:
                cmd.extend(["--db-url", args.db_url])
            if args.db_container:
                cmd.extend(["--db-container", args.db_container])
            if args.db_user:
                cmd.extend(["--db-user", args.db_user])
            if args.db_name:
                cmd.extend(["--db-name", args.db_name])

            print(f"[manifest] loading row {idx}: {project_code} {report_type} {report_date}")
            proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
            if proc.returncode != 0:
                failures += 1
                print(f"[manifest] row {idx} failed with exit code {proc.returncode}", file=sys.stderr)
                if not args.continue_on_error:
                    return 1

    if args.preflight_only:
        print(
            f"[preflight] checked={preflight_checked} missing={preflight_missing} "
            f"manifest={args.manifest_path}"
        )
        return 1 if preflight_missing else 0

    if failures:
        print(f"[manifest] completed with {failures} failure(s)", file=sys.stderr)
        return 1
    print("[manifest] completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
