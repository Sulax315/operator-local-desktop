# Weekly operator cycle runbook

This runbook defines the deterministic weekly operating cycle for new schedule exports in Bratek Operator Stack.

## Guardrails (non-negotiable)

- PostgreSQL is the sole truth layer for schedule logic and comparison semantics.
- Python and JS remain projection-only.
- ECharts surfaces are read-only visual projections of SQL truth.
- Computed path is non-authoritative and must not be treated as engine truth.
- Prior snapshots are append-only history and must never be overwritten.

## Weekly wrapper command (primary entrypoint)

Use the weekly wrapper as the default operator command:

```bash
cd /srv/operator-stack-clean
python3 scripts/operator_run_weekly_cycle.py \
  --csv /data/exports/schedule_2026-04-15_wk16_asta_main.csv \
  --snapshot-date 2026-04-15
```

### Required arguments

- `--csv <path>`: weekly schedule export CSV file.
- `--snapshot-date YYYY-MM-DD`: target append-only snapshot date.

### Optional arguments

- `--prior-snapshot-date YYYY-MM-DD`: explicit compare baseline.
- `--skip-load`: skip load step (when snapshot is already present).
- `--skip-refresh`: skip SQL refresh step.
- `--skip-validation`: skip wrapper validation checks.
- `--database-url <postgres-uri>`: use host `psql` URI mode for SQL execution.
- `--db-container <name>`: explicit container for docker exec mode.
- `--db-user <user>` / `--db-name <db>`: container DB credentials.
- `--db-container-for-load <name>`: load-step-only `DB_CONTAINER`.
- `--load-script <path>`: override loader script path.
- `--load-label <label>`: override default `weekly_cycle_<snapshot_date>`.
- `--base-url <url>`: review URL base (default `http://127.0.0.1:8090`).
- `--audit-dir <path>`: audit output directory.

## Weekly input naming convention

Use stable, explicit names for each weekly package:

- Schedule export CSV:
  - `schedule_<snapshot_date>_wk<iso_week>_<source_tag>.csv`
  - Example: `schedule_2026-04-15_wk16_asta_main.csv`
- Optional driver-path export CSV:
  - `asta_driver_path_<snapshot_date>_wk<iso_week>_<run_id>.csv`
  - Example: `asta_driver_path_2026-04-15_wk16_run1.csv`
- Load labels:
  - `asta_schedule_<snapshot_date>_wk<iso_week>`
  - Example: `asta_schedule_2026-04-15_wk16`

Use ISO `YYYY-MM-DD` for every `snapshot_date` and keep that same date across load, refresh, and review.

## Weekly sequence (authoritative flow)

1) Receive new export CSV

- Confirm file origin, export timestamp, and expected project/scope coverage.
- Verify UTF-8 encoding and expected header contract before loading.

2) Upload/load as a new `snapshot_date`

- Choose the new weekly `snapshot_date` (for example `2026-04-15`).
- Never reuse prior snapshot dates for a new week.

3) Run append-only load

- Execute schedule ingest with a new `LOAD_LABEL` and the new `SNAPSHOT_DATE`.
- Do not delete prior snapshots.
- Wrapper default `LOAD_LABEL` is `weekly_cycle_<snapshot_date>` unless overridden.

```bash
cd /srv/operator-stack-clean
export SNAPSHOT_DATE='2026-04-15'
export LOAD_LABEL='asta_schedule_2026-04-15_wk16'
export CSV_LOCAL='/data/exports/schedule_2026-04-15_wk16_asta_main.csv'
bash scripts/phase2_load_and_signals.sh
```

Preferred wrapper equivalent:

```bash
python3 scripts/operator_run_weekly_cycle.py \
  --csv /data/exports/schedule_2026-04-15_wk16_asta_main.csv \
  --snapshot-date 2026-04-15
```

4) Refresh graph / computed path / comparison artifacts

- Dependency graph normalization:
  - `sql/06_refresh_dependency_graph.sql`
- Computed path refresh:
  - `sql/07_refresh_computed_driver_path.sql`
- Path comparison/operator signals:
  - `sql/04_signals.sql` (if needed after schema/view changes)

Example:

```bash
DB_CONTAINER='bratek-phase1-postgres'
DB_USER='bratek_ops'
DB_NAME='postgres'

docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < sql/06_refresh_dependency_graph.sql
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < sql/07_refresh_computed_driver_path.sql
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < sql/04_signals.sql
```

5) Compare current snapshot to prior snapshot

- The system uses `v_schedule_snapshot_pair_latest`:
  - `current_snapshot_date` = newest loaded week
  - `prior_snapshot_date` = immediately previous week
- Example API-driven compare filters:
  - `/path-comparison?compare_from_snapshot=2026-04-08&compare_to_snapshot=2026-04-15`

6) Review summary strip first (weekly first look)

- Start at `/path-comparison`.
- First check:
  - P1 total
  - dominant overall classification
  - dominant P1 subtype
- This sets weekly focus before row-level triage.

7) Review P1 triage

- In the P1 table, review:
  - `classification_reason`
  - `operator_action_hint`
  - `operator_priority_reason`
  - `classification_evidence`

8) Drill into selected rows

- From each P1 row use drill links:
  - dependency/context view:
    - `/path-comparison?task_id=<task_id>`
  - computed projection:
    - `/computed-path?task_id=<task_id>`
  - critical projection:
    - `/critical-path?task_id=<task_id>`
- Additional deterministic filters:
  - `/path-comparison?priority=P1`
  - `/path-comparison?classification_reason=critical_with_logic_gap_downstream`
  - `/path-comparison?operator_priority_band=P1`
  - `/path-comparison?snapshot_date=2026-04-15`

After wrapper completion, open these first:

1. `/path-comparison?compare_from_snapshot=<prior>&compare_to_snapshot=<current>`
2. `/path-comparison?priority=P1&compare_from_snapshot=<prior>&compare_to_snapshot=<current>`
3. Optional task example links emitted by wrapper audit/console (if a P1 task is available):
   - `/path-comparison?task_id=<task_id>`
   - `/computed-path?task_id=<task_id>`
   - `/critical-path?task_id=<task_id>`

9) Record operator findings/actions

- For each investigated task, record:
  - `snapshot_date`
  - `task_id`
  - classification and priority at review time
  - action taken / escalation decision
  - operator notes and owner
- Keep notes in the weekly operations log or handoff artifact (append-only).

10) Preserve prior snapshots without overwrite

- Validate that prior snapshots are still queryable.
- Do not truncate snapshot history as part of weekly cycle.
- Any correction should be a new load/event, not a destructive rewrite.

## Snapshot date usage examples

- Week 15 loaded as: `snapshot_date = 2026-04-08`
- Week 16 loaded as: `snapshot_date = 2026-04-15`
- Weekly compare:
  - current = `2026-04-15`
  - prior = `2026-04-08`

## Operator weekly start checklist

Review in this order every week:

1. `/path-comparison` summary strip
2. P1 triage subtype counts
3. Top-risk P1 rows
4. Task drill-in context for selected IDs
5. Computed vs critical filtered views for those same IDs

## Weekly done criteria

A weekly cycle is done when all conditions are true:

- New export was loaded to a new `snapshot_date` (append-only).
- Graph + computed + comparison refresh completed without SQL errors.
- Current/prior snapshot pair is visible and correct.
- Summary strip + full P1 triage reviewed.
- Drill-in investigation completed for selected P1 tasks.
- Findings/actions were recorded with snapshot and task IDs.
- Prior snapshot data remains intact and queryable.

Wrapper-level success criteria:

- Console prints:
  - `OVERALL_STATUS: PASS`
  - resolved `snapshot_date` and `prior_snapshot_date`
  - status lines for `load_status`, `refresh_status`, `validation_status`
  - review URLs for comparison and P1 triage
  - `Audit written: <path>`
- Audit JSON exists at:
  - `runtime/operator_audit/operator_run_weekly_cycle_<timestamp>.json`
- Audit includes:
  - `run_started_at`
  - `run_finished_at`
  - `overall_status`
  - `snapshot_date`
  - `prior_snapshot_date`
  - `csv_path`
  - `load_status`
  - `refresh_status`
  - `validation_status`
  - `output_urls`
  - `error_messages`
