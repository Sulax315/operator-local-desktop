# Week-over-week schedule drift runbook

## Purpose

Run a repeatable weekly cycle that:

1. loads a new ASTA snapshot export into Postgres,
2. refreshes WoW delta/signal views,
3. publishes Metabase questions and dashboard tiles,
4. validates key reconciliation checks.

## Prerequisites

- Postgres reachable by one mode:
  - `--database-url` (or `OPERATOR_DATABASE_URL` / `DATABASE_URL`), or
  - Docker container mode (`bratek-phase1-postgres` by default).
- ASTA export CSV with the contract in `docs/schedule_wow_data_contract.md`.
- Metabase environment configured (`METABASE_*` variables).

## One-time setup

1. Ensure SQL/view files are present:
   - `sql/04_signals.sql`
   - `sql/17_schedule_wow_signals.sql`
2. Ensure scripts are executable/available:
   - `scripts/load_schedule_snapshot_export.py`
   - `scripts/publish_schedule_wow_metabase.py`

## Weekly operator sequence

### 1) Place weekly export

Drop the file in `data/` (or another local path).

Example:

```bash
ls data/EXPORT_*.csv
```

### 2) Load and refresh signals

```bash
python3 scripts/load_schedule_snapshot_export.py \
  --csv-path data/EXPORT_003-2026-04-09_UTF8.csv \
  --snapshot-date 2026-04-09 \
  --load-label "asta-weekly-2026-04-09"
```

Notes:

- Add `--database-url "$OPERATOR_DATABASE_URL"` for URI mode.
- Add `--skip-schema` if schema re-apply is not desired on the run.
- The script prints JSON summary with per-step success/failure.

### 3) Publish Metabase content

```bash
python3 scripts/publish_schedule_wow_metabase.py \
  --env-file config/metabase_publish.env
```

Dry run:

```bash
python3 scripts/publish_schedule_wow_metabase.py \
  --env-file config/metabase_publish.env \
  --dry-run
```

### 4) Optional guarded wrapper run

If running wrapper-based validation and publication pipeline:

```bash
python3 scripts/operator_run_snapshot_cycle.py \
  --skip-load \
  --publish-script scripts/publish_schedule_wow_metabase.py \
  --metabase-env-file config/metabase_publish.env
```

## Validation checklist

Run these checks after load/publish:

1. Snapshot pair present:

```sql
SELECT * FROM v_schedule_snapshot_pair_latest;
```

2. WoW row count non-zero:

```sql
SELECT COUNT(*) FROM v_schedule_wow_task_delta_latest_pair;
```

3. KPI reconciles with base:

```sql
SELECT
  k.slipped_task_count,
  (SELECT COUNT(*) FROM v_schedule_wow_task_delta_latest_pair WHERE status_change_class = 'slipped') AS slipped_from_base
FROM v_schedule_wow_kpi_strip k;
```

4. Top-risk output populated:

```sql
SELECT *
FROM v_schedule_wow_top_risk_tasks
LIMIT 10;
```

5. Metabase rerun idempotency:
- rerun publisher,
- confirm no duplicate cards are created,
- confirm dashboard keeps one tile per WoW question.

## Published visualization set

The publisher upserts these cards:

- `WoW Snapshot Pair`
- `WoW KPI Strip`
- `WoW Slip Distribution`
- `WoW Critical Transition Matrix`
- `WoW Change Class Waterfall`
- `WoW Phase-Control Heatmap`
- `WoW Top Risk Tasks`
- `WoW Timeline Drilldown`

## Troubleshooting

- Header mismatch on load:
  - verify the CSV header row exactly matches ASTA contract columns.
- SQL view failure:
  - re-run `sql/04_signals.sql` then `sql/17_schedule_wow_signals.sql`.
- Metabase auth errors:
  - verify `METABASE_API_KEY` or username/password.
- Missing dashboard:
  - set `METABASE_DASHBOARD_ID` or a valid `METABASE_DASHBOARD_NAME`.
