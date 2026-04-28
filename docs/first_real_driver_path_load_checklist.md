# First real Asta driver-path load checklist

Purpose: run the first **real** Asta driver-path ingest with minimal ambiguity and no fake data.

Scope boundary:
- Uses existing truth-layer ingest only (`schedule_driver_path_staging` -> `schedule_driver_path`).
- Does **not** create `v_operator_driver_path_current`.
- Does **not** add UI/ECharts behavior.
- Does **not** derive path logic from `predecessors`/`successors`.

Authoritative references:
- `docs/driver_path_data_contract.md`
- `docs/driver_path_ingest_runbook.md`
- `scripts/load_driver_path_export.py`
- `scripts/validate_driver_path_load.py`
- `scripts/driver_path_first_load_check.py`

## 1) Required files before execution

- **Schedule CSV** for snapshot `YYYY-MM-DD` (the same one that populates `schedule_tasks`).
- **Driver-path CSV** exported by Asta for the same snapshot date.
- Optional but recommended:
  - Export metadata (run id, export timestamp, tool/version provenance).
  - File checksum record for operator audit.

Minimum required driver-path columns in CSV header:
- `path_sequence`
- `task_id`
- `snapshot_date`
- `path_scope`
- `start_date`
- `finish_date`
- `total_float`
- `critical`
- `run_id`

## 2) Naming expectations

- `SNAPSHOT_DATE` is ISO date: `YYYY-MM-DD`.
- One `run_id` per driver-path file; every row carries the same non-empty `run_id`.
- Use explicit load labels (examples):
  - `asta_schedule_YYYY-MM-DD_main`
  - `asta_driver_path_YYYY-MM-DD_run1`
- Suggested filename pattern (not loader-enforced):
  - `schedule_YYYY-MM-DD.csv`
  - `asta_driver_path_YYYY-MM-DD_run1.csv`

## 3) Snapshot alignment checks (pre-load gate)

Run this before loading driver path:

```bash
python3 scripts/driver_path_first_load_check.py \
  --phase pre \
  --snapshot-date "$SNAPSHOT_DATE" \
  --csv-path "$DRIVER_PATH_CSV" \
  --db-container "$DB_CONTAINER"
```

Required result:
- `PASS` for schedule snapshot presence (`schedule_tasks` has rows for `SNAPSHOT_DATE`).
- `PASS` for required driver-path columns present.
- `PASS` for no unknown columns outside the loader allowlist.

If any pre-check fails: **STOP** and fix export/inputs before ingest.

## 4) Exact command order (first real load)

```bash
export DB_CONTAINER='bratek-phase1-postgres'
export SNAPSHOT_DATE='YYYY-MM-DD'
export SCHEDULE_CSV='/absolute/path/to/schedule_YYYY-MM-DD.csv'
export DRIVER_PATH_CSV='/absolute/path/to/asta_driver_path_YYYY-MM-DD_run1.csv'

# 1) Load schedule first (truth register)
export LOAD_LABEL="asta_schedule_${SNAPSHOT_DATE}_main"
export CSV_LOCAL="$SCHEDULE_CSV"
bash scripts/phase2_load_and_signals.sh

# 2) Pre-load gate
python3 scripts/driver_path_first_load_check.py \
  --phase pre \
  --snapshot-date "$SNAPSHOT_DATE" \
  --csv-path "$DRIVER_PATH_CSV" \
  --db-container "$DB_CONTAINER"

# 3) Load driver-path export
export LOAD_LABEL="asta_driver_path_${SNAPSHOT_DATE}_run1"
python3 scripts/load_driver_path_export.py \
  --csv-path "$DRIVER_PATH_CSV" \
  --snapshot-date "$SNAPSHOT_DATE" \
  --load-label "$LOAD_LABEL" \
  --db-container "$DB_CONTAINER"

# 4) Validate load summary
python3 scripts/validate_driver_path_load.py \
  --snapshot-date "$SNAPSHOT_DATE" \
  --db-container "$DB_CONTAINER" \
  --sample-limit 50

# 5) Post-load gate
python3 scripts/driver_path_first_load_check.py \
  --phase post \
  --snapshot-date "$SNAPSHOT_DATE" \
  --db-container "$DB_CONTAINER"
```

## 5) Expected PASS outputs

Expected terminal signals:
- `scripts/load_driver_path_export.py` prints:
  - `PASS: driver-path rows promoted to schedule_driver_path`
- `scripts/driver_path_first_load_check.py --phase pre` prints:
  - `PASS: schedule_tasks has rows for snapshot_date ...`
  - `PASS: driver-path CSV contains required contract columns`
  - `PASS: CSV columns are in loader allowlist`
- `scripts/driver_path_first_load_check.py --phase post` prints:
  - `PASS: inventory has driver-path rows for snapshot_date ...`
  - `PASS: every run has contiguous sequence bounds (min=1 and max=row_count)`

## 6) Post-load SQL spot-check block

Run this exact block after a PASS ingest:

```sql
-- Inventory by scope/run for this snapshot
SELECT
  snapshot_date,
  path_scope,
  run_id,
  row_count,
  min_path_sequence,
  max_path_sequence,
  distinct_task_count,
  latest_run_id_for_scope,
  latest_run_id_for_snapshot
FROM v_schedule_driver_path_inventory
WHERE snapshot_date = DATE 'YYYY-MM-DD'
ORDER BY path_scope, run_id;

-- First 50 path rows in authoritative order
SELECT
  snapshot_date,
  path_scope,
  run_id,
  path_sequence,
  task_id,
  task_name,
  start_date,
  finish_date,
  total_float_days,
  critical
FROM schedule_driver_path
WHERE snapshot_date = DATE 'YYYY-MM-DD'
ORDER BY path_scope, run_id, path_sequence
LIMIT 50;
```

## 7) What to compare in Asta UI

For the same snapshot and path report used for export:
- Path membership: the same tasks appear in Asta and Postgres.
- Path order: Asta order matches `ORDER BY path_scope, run_id, path_sequence`.
- Scope mapping: each exported chain uses correct `path_scope` values.
- Row count sanity: count in Asta report is consistent with `row_count`.
- Edge cases: first/last few tasks and any major handoff tasks match exactly.

If Asta and Postgres disagree on order/membership: **STOP** and fix export settings or source file. Do not patch order in SQL/Python/JS.

## 8) Go / no-go decision criteria

Go to next implementation step (defining `v_operator_driver_path_current`) only when all are true:
- At least one real Asta export ingested successfully for an operational snapshot.
- Pre and post gate checks pass.
- Loader PASS and validator output are clean and expected.
- Manual Asta-vs-Postgres order check is signed off by operator/owner.
- Governance decision exists for canonical `path_scope` and tie-break for `run_id`.

No-go (stop and fix data/contract) when any are true:
- Pre-gate fails (missing schedule snapshot, header mismatch, unknown columns).
- Ingest fails or rolls back.
- Inventory shows zero rows for target snapshot.
- Sequence bounds are inconsistent (`min_path_sequence != 1` or `max_path_sequence != row_count` for any run).
- Asta order/membership does not match loaded path rows.
- `run_id` usage is inconsistent or ambiguous for the same snapshot/scope.
