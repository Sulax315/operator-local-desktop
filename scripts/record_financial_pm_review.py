#!/usr/bin/env python3
"""
Insert a financial_pm_review_event row (monthly PM + field review log).
Uses same DB connection env as operator_echarts: DATABASE_URL or PG* vars.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import quote_plus

try:
    import psycopg
except ImportError:
    print("Install psycopg: pip install psycopg[binary]", file=sys.stderr)
    raise SystemExit(2) from None


def _database_url() -> str:
    direct = os.environ.get("DATABASE_URL", "").strip()
    if direct:
        return direct
    host = os.environ.get("PGHOST", "localhost").strip()
    port = os.environ.get("PGPORT", "5432").strip()
    db = os.environ.get("PGDATABASE", os.environ.get("POSTGRES_DB", "postgres")).strip()
    user = os.environ.get("PGUSER", os.environ.get("POSTGRES_USER", "")).strip()
    pwd = os.environ.get("PGPASSWORD", os.environ.get("POSTGRES_PASSWORD", "")).strip()
    if not user:
        raise SystemExit("Set DATABASE_URL or PGUSER and PGPASSWORD")
    return f"postgresql://{quote_plus(user)}:{quote_plus(pwd)}@{host}:{port}/{quote_plus(db)}"


def main() -> None:
    p = argparse.ArgumentParser(description="Log a PM+field financial review event.")
    p.add_argument("project_code", help="Job code (alphanumeric, _, -)")
    p.add_argument("--actor", default="", help="Person or system id")
    p.add_argument("--notes", default="", help="Optional note")
    p.add_argument(
        "--at",
        dest="reviewed_at",
        default="",
        help="ISO timestamp (default: now UTC)",
    )
    args = p.parse_args()
    pc = args.project_code.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", pc):
        raise SystemExit("invalid project_code")
    if args.reviewed_at.strip():
        reviewed_at = datetime.fromisoformat(args.reviewed_at.replace("Z", "+00:00"))
    else:
        reviewed_at = datetime.now(timezone.utc)
    with psycopg.connect(_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO financial_pm_review_event (project_code, reviewed_at, actor, notes)
                VALUES (%(pc)s, %(at)s, %(actor)s, %(notes)s)
                """,
                {
                    "pc": pc,
                    "at": reviewed_at,
                    "actor": args.actor.strip() or None,
                    "notes": args.notes.strip() or None,
                },
            )
        conn.commit()
    print(f"OK: logged review for {pc} at {reviewed_at.isoformat()}")


if __name__ == "__main__":
    main()
