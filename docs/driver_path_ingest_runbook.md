# Driver path ingest — runbook

This runbook covers **truth-layer ingestion** of an **engine-authoritative** driver-path export into PostgreSQL. It does **not** define visualization, pathfinding, or any ordering derived from `predecessors` / `successors` text.

**Normative contract:** `docs/driver_path_data_contract.md` (especially §8).

**Governance:** PostgreSQL remains the sole truth layer (`MASTER-PLAN-UPDATED-V5.txt`).

**First real export checklist:** `docs/first_real_driver_path_load_checklist.md` (operator go/no-go gate).

---

## Prerequisites

1. **Schema applied** — `sql/01_schema.sql` has been executed at least once on the target database so that `schedule_driver_path_staging`, `schedule_driver_path`, and `v_schedule_driver_path_inventory` exist. **Note:** `01_schema.sql` drops and recreates schedule-related views at the top; if you run it **outside** `scripts/phase2_load_and_signals.sh`, re-apply `sql/04_signals.sql` afterward so `v_operator_critical_path_current` and other operator views are restored.
2. **Schedule snapshot loaded first** — `schedule_tasks` must already contain rows for the target `snapshot_date` (same pattern as `sql/03_insert_schedule_tasks.sql` / `scripts/phase2_load_and_signals.sh`). Driver-path rows **reference** `(snapshot_date, task_id)` on `schedule_tasks` via a foreign key.
3. **Client tooling** — `psql` on the host when using `--database-url` / `OPERATOR_DATABASE_URL`, **or** Docker with a running Postgres container when using `--db-container`.
4. **Authoritative export** — A CSV produced by the scheduling engine (or an engine-faithful extract) that supplies **`path_sequence` from the tool**, not invented in Bratek code.

Until such a file exists in production, **do not** point Metabase, ECharts, or any “driver path” UI at this dataset. **`v_operator_driver_path_current` is intentionally not implemented** until program governance selects “current” scope rules on top of real ingested truth (see **Go-live criteria for `v_operator_driver_path_current`** below).

---

## Operator workflow (end-to-end)

Use this sequence whenever a new **schedule snapshot** and matching **Asta driver-path export** arrive.

### 0. Optional operator gate (read-only precheck)

Before loading the driver-path CSV, run:

```bash
python3 scripts/driver_path_first_load_check.py \
  --phase pre \
  --snapshot-date "$SNAPSHOT_DATE" \
  --csv-path /path/to/asta_driver_path_export.csv \
  --db-container "$DB_CONTAINER"
```

This reduces first-load mistakes by confirming schedule snapshot presence plus CSV contract/allowlist headers.

### 1. Load schedule (truth register)

Load the schedule CSV for the snapshot so `schedule_tasks` is populated **before** any driver-path file (FK requirement).

```bash
export SNAPSHOT_DATE='YYYY-MM-DD'
export LOAD_LABEL='asta_schedule_YYYY-MM-DD_<short_note>'
export CSV_LOCAL='/path/to/schedule_export.csv'
export DB_CONTAINER='bratek-phase1-postgres'   # or your compose-resolved name

bash scripts/phase2_load_and_signals.sh
```

Confirm row counts / views at the end of the script output, or run a quick `psql` count on `schedule_tasks` for `SNAPSHOT_DATE`.

### 2. Load driver path (engine path order)

Use the **same** `SNAPSHOT_DATE` as the schedule load. `run_id` must be stable and unique to this path export run.

```bash
python3 scripts/load_driver_path_export.py \
  --csv-path /path/to/asta_driver_path_export.csv \
  --snapshot-date "$SNAPSHOT_DATE" \
  --load-label 'asta_driver_path_'"$SNAPSHOT_DATE"'_<run_note>' \
  --db-container "$DB_CONTAINER"
```

Expect stdout: `PASS: driver-path rows promoted to schedule_driver_path`. On `FAIL`, the whole ingest transaction rolls back — fix the CSV or schedule alignment and retry.

### 3. Validate (read-only)

Summarizes `schedule_driver_path` for the **latest** snapshot present in the table (or pass `--snapshot-date`).

```bash
python3 scripts/validate_driver_path_load.py --db-container "$DB_CONTAINER"
# or explicit snapshot:
python3 scripts/validate_driver_path_load.py --snapshot-date "$SNAPSHOT_DATE" --db-container "$DB_CONTAINER"
```

Check that the row count is greater than zero, `min_seq` / `max_seq` look coherent, the `path_scope` list matches what Asta exported, and sample rows show the expected `task_id` / `path_sequence` order.

### 3b. Optional operator gate (read-only postcheck)

```bash
python3 scripts/driver_path_first_load_check.py \
  --phase post \
  --snapshot-date "$SNAPSHOT_DATE" \
  --db-container "$DB_CONTAINER"
```

Expected outputs include:
- `PASS: inventory has driver-path rows for snapshot_date ...`
- `PASS: every run has contiguous sequence bounds (min=1 and max=row_count)`

### 4. Confirm alignment (human gate)

- In **Asta** (or the engine UI), open the same snapshot and the same driving-path / longest-path report used to produce the CSV.
- Compare task order to Postgres: `ORDER BY path_scope, run_id, path_sequence` (e.g. widen the sample limit: `--sample-limit 50`).
- Optionally compare counts and latest run metadata:

```sql
SELECT * FROM v_schedule_driver_path_inventory
WHERE snapshot_date = DATE 'YYYY-MM-DD'
ORDER BY path_scope, run_id;
```

`latest_run_id_for_scope` / `latest_run_id_for_snapshot` use **`MAX(export_timestamp_utc)`** per path scope or per snapshot (ties broken by `path_scope` / `run_id`) — if exports omit timestamps, treat those columns as weak ordering hints and rely on `run_id` + file audit instead.

---

## Example command sequence (copy-paste template)

```bash
export DB_CONTAINER='bratek-phase1-postgres'
export SNAPSHOT_DATE='2026-04-09'
export SCHEDULE_CSV="/data/exports/schedule_${SNAPSHOT_DATE}.csv"
export DRIVER_PATH_CSV="/data/exports/asta_driver_path_${SNAPSHOT_DATE}.csv"

export LOAD_LABEL="asta_schedule_${SNAPSHOT_DATE}_main"
export CSV_LOCAL="$SCHEDULE_CSV"
bash scripts/phase2_load_and_signals.sh

export LOAD_LABEL="asta_driver_path_${SNAPSHOT_DATE}_run1"
python3 scripts/load_driver_path_export.py \
  --csv-path "$DRIVER_PATH_CSV" \
  --snapshot-date "$SNAPSHOT_DATE" \
  --load-label "$LOAD_LABEL" \
  --db-container "$DB_CONTAINER"

python3 scripts/validate_driver_path_load.py --snapshot-date "$SNAPSHOT_DATE" --db-container "$DB_CONTAINER"
```

Adjust paths, container name, and labels to your environment.

---

## Post-load SQL spot-check block (copy-paste)

Use this block after a PASS ingest and validation:

```sql
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

---

## Troubleshooting

### Foreign key failure (`schedule_driver_path_tasks_fk`)

**Symptom:** Promotion or insert errors mentioning `schedule_driver_path_tasks_fk` or `violates foreign key constraint`.

**Cause:** A `task_id` on the driver-path CSV is not present in `schedule_tasks` for the same `snapshot_date` (wrong snapshot, stale CSV, trimmed IDs, or schedule load not run).

**Fix:** Reload schedule for that `snapshot_date` first; ensure Asta exports **identical** task IDs to the schedule CSV; re-export driver path from the same snapshot job.

### Sequence gaps / duplicate sequence

**Symptom:** `FAIL: path_sequence must be contiguous 1..N per (path_scope, run_id)` or unique violation on `(snapshot_date, path_scope, run_id, path_sequence)`.

**Cause:** Truncated export, merged cells, manual edits, or multiple paths concatenated with the same `path_scope` / `run_id`.

**Fix:** Re-export from Asta; ensure one `run_id` per file; use distinct `path_scope` values when the engine emits multiple chains in one job (per contract §8.6).

### Mismatched snapshot

**Symptom:** `FAIL: snapshot_date … not equal to expected` or `FAIL: no schedule_tasks rows for snapshot_date`.

**Cause:** Driver-path CSV `snapshot_date` column disagrees with `--snapshot-date`, or schedule was never loaded for that date.

**Fix:** Align `SNAPSHOT_DATE` / `__BRA_SNAPSHOT__` workflow with the schedule load; use the same calendar date the program uses for `schedule_tasks` (see `sql/03_insert_schedule_tasks.sql`).

### `INSERT … ON CONFLICT DO NOTHING` / row count verification

**Symptom:** `FAIL: after insert, not every promoted row is present…`

**Cause:** Re-ingesting the same `(snapshot_date, path_scope, run_id, path_sequence)` as an existing row — promotion skips the insert but staging still expects full coverage.

**Fix:** Use a **new** `run_id` for each distinct export run, or clear old truth rows only under explicit program policy (not automated here).

---

## Go-live criteria for `v_operator_driver_path_current`

Do **not** add or enable `v_operator_driver_path_current` in this repo until **all** of the following are true:

1. **Real engine export in production** — At least one driver-path CSV (or equivalent ingest) produced by **Asta** (or the governed scheduler), not synthetic test data, is loaded into `schedule_driver_path` for an operational snapshot.
2. **Scheduler UI cross-check** — A responsible operator has compared Asta’s driving-path / longest-path task order to Postgres `ORDER BY path_scope, run_id, path_sequence` for the same `path_scope` and snapshot; discrepancies are resolved at the **export** side, not by reordering in SQL or Python.
3. **Clean validation** — `scripts/load_driver_path_export.py` completes with **PASS** for that file; `scripts/validate_driver_path_load.py` shows the expected row count and sequence bounds; `v_schedule_driver_path_inventory` matches expectations for `row_count`, `max_path_sequence`, and `distinct_task_count`.
4. **`path_sequence` trusted** — Program sign-off that `path_sequence` is **engine-authoritative** for the configured export pipeline (contract `docs/driver_path_data_contract.md` §1, §8). No derivation from `predecessors` / `successors` text.
5. **Governance for “current”** — Written decision on which `path_scope` (and how to choose the canonical `run_id` when multiple exist) defines **operator “current”** — only then does a `v_operator_driver_path_current` view become meaningful.

Until then, keep using **`v_operator_critical_path_current`** only for critical incomplete tasks; it is **not** a driver path.

---

## Expected file format

- **Encoding:** UTF-8 (BOM tolerated via `utf-8-sig` header read in the loader; `psql` `\copy` uses `ENCODING 'UTF8'`).
- **Delimiter / quoting:** RFC 4180 CSV (comma; quotes for embedded commas/newlines).
- **Header row:** snake_case column names. **Required columns** (loader-enforced):

  `path_sequence`, `task_id`, `snapshot_date`, `path_scope`, `start_date`, `finish_date`, `total_float`, `critical`, `run_id`

- **Column order:** Positional `\copy` mapping — **every** column in the file header must be a known staging column (see loader allowlist in `scripts/load_driver_path_export.py`). Unknown columns are rejected. Optional columns from the contract may be omitted entirely (not present in the header).
- **Dates on path rows:** `YYYY-MM-DD` only for `snapshot_date`, `start_date`, and `finish_date` in v1 promotion SQL.
- **`snapshot_date` column:** Every data row must equal the `--snapshot-date` argument and match the loaded `schedule_tasks` snapshot.
- **`run_id`:** Must be **non-empty and identical on every row** in the file (one export run per file for this loader).
- **`path_sequence`:** Integer ≥ 1, **unique** per `(snapshot_date, path_scope, run_id)`, **contiguous** `1..N` per `(path_scope, run_id)` (no gaps unless the program explicitly adopts a different contract).
- **`task_id`:** Non-empty after `TRIM`; must **exist** in `schedule_tasks` for the same `snapshot_date` (byte identity after trim, same as schedule CSV).
- **`path_scope`:** Non-empty after `TRIM` (disambiguates multiple engine paths).
- **`total_float`:** Numeric after stripping non-numeric characters (same spirit as schedule ingest); must parse to a non-null `numeric`.
- **`critical`:** Non-empty after `TRIM` (empty is a validation failure here).

Recommended optional columns (stored when present): `task_name`, `path_source`, `export_timestamp_utc`, `tool_name`, `tool_version`, `project_id`, `source_filename`, `source_file_sha256`.

`load_label` may appear in the CSV but is **ignored for COPY**; the CLI `--load-label` value is stamped on all staging rows before promotion for audit alignment.

---

## How to load an authoritative driver-path export

From the repo root:

```bash
python3 scripts/load_driver_path_export.py \
  --csv-path /path/to/driver_path_export.csv \
  --snapshot-date YYYY-MM-DD \
  --load-label 'asta_driver_path_2026-04-09_run1' \
  --database-url "$OPERATOR_DATABASE_URL"
```

Docker transport (Compose-style container name):

```bash
python3 scripts/load_driver_path_export.py \
  --csv-path /path/to/driver_path_export.csv \
  --snapshot-date YYYY-MM-DD \
  --load-label 'asta_driver_path_2026-04-09_run1' \
  --db-container bratek-phase1-postgres
```

Optional JSON audit log:

```bash
python3 scripts/load_driver_path_export.py \
  --csv-path /path/to/driver_path_export.csv \
  --snapshot-date YYYY-MM-DD \
  --load-label 'my_audit_label' \
  --database-url "$OPERATOR_DATABASE_URL" \
  --audit-json runtime/operator_audit/driver_path_ingest.json
```

**What happens**

1. Loader verifies required headers and rejects unknown CSV columns.
2. A **single `psql -1` transaction** runs: `TRUNCATE schedule_driver_path_staging` → client/server `\copy` into staging → `UPDATE` to set `load_label` → `sql/05_insert_driver_path.sql` (typed temp projection, validation `DO` blocks, `INSERT … ON CONFLICT DO NOTHING` into `schedule_driver_path`, final row-coverage check).
3. On success, stdout prints `PASS:`; on failure, stderr explains the first failing check (or Postgres error) and the transaction rolls back.

---

## Validation checks

| Check | Where |
| ----- | ----- |
| Required CSV headers present; no unknown columns | `scripts/load_driver_path_export.py` |
| `snapshot_date` format `YYYY-MM-DD` argument | `scripts/load_driver_path_export.py` |
| Staging non-empty | `sql/05_insert_driver_path.sql` |
| Every staging row normalizes into `tmp_driver_path_promoted` (non-null `task_id` after trim) | `sql/05_insert_driver_path.sql` |
| `snapshot_date` text valid ISO and equals expected snapshot | `sql/05_insert_driver_path.sql` |
| `schedule_tasks` has at least one row for expected `snapshot_date` | `sql/05_insert_driver_path.sql` |
| `path_scope` non-empty | `sql/05_insert_driver_path.sql` |
| `path_sequence` integer ≥ 1; no duplicates per `(snapshot_date, path_scope, run_id)` | `sql/05_insert_driver_path.sql` + PK |
| No duplicate `task_id` per `(snapshot_date, path_scope, run_id)` | `sql/05_insert_driver_path.sql` + UNIQUE |
| Exactly one distinct non-null `run_id` across rows | `sql/05_insert_driver_path.sql` |
| Every `task_id` exists in `schedule_tasks` for the snapshot | `sql/05_insert_driver_path.sql` |
| `start_date` / `finish_date` ISO and non-null after parse | `sql/05_insert_driver_path.sql` |
| `total_float` parses to non-null numeric | `sql/05_insert_driver_path.sql` |
| `critical` non-empty | `sql/05_insert_driver_path.sql` |
| Contiguous `path_sequence` `1..N` per `(path_scope, run_id)` | `sql/05_insert_driver_path.sql` |
| After insert, every promoted row exists in `schedule_driver_path` by PK (covers `ON CONFLICT DO NOTHING` drift) | `sql/05_insert_driver_path.sql` |
| Referential integrity on new inserts | FK `schedule_driver_path` → `schedule_tasks` |
| Post-ingest row counts, scopes, sample rows (operator) | `scripts/validate_driver_path_load.py` |

**Neutral inventory (not a “current driver path” view):**

```sql
SELECT * FROM v_schedule_driver_path_inventory;
```

Columns include **`row_count`**, **`min_path_sequence`**, **`max_path_sequence`**, **`distinct_task_count`** (per `snapshot_date` + `path_scope` + `run_id`), plus **`latest_run_id_for_scope`** (newest `export_timestamp_utc` within that scope, tie-break `run_id`) and **`latest_run_id_for_snapshot`** (newest timestamp across all scopes for that snapshot). If exports omit `export_timestamp_utc`, use these columns cautiously and prefer `run_id` + file provenance from the ingest audit trail.

---

## Failure modes (operator-facing)

| Symptom | Typical cause |
| ------- | ------------- |
| `FAIL: schedule_driver_path_staging is empty` | Empty CSV or `\copy` saw zero data rows |
| `FAIL: snapshot_date … not equal to expected` | CSV `snapshot_date` does not match `--snapshot-date` |
| `FAIL: no schedule_tasks rows for snapshot_date` | Schedule not loaded for that date |
| `FAIL: path_scope required` | Blank `path_scope` |
| `FAIL: duplicate path_sequence…` / unique violation | Engine export duplicated a sequence index |
| `FAIL: duplicate task_id…` / unique violation | Same task repeated on one path instance |
| `FAIL: run_id must be non-empty and identical…` | Mixed or missing `run_id` |
| `FAIL: … task_id rows are not present in schedule_tasks` | IDs do not match schedule import |
| `FAIL: start_date and finish_date must be present ISO…` | Wrong date format or blank |
| `FAIL: total_float … required` | Unparseable float |
| `FAIL: critical required` | Blank critical flag |
| `FAIL: path_sequence must be contiguous…` | Gaps or wrong min/max relative to row count |
| `invalid input syntax for type integer/numeric/date` | Malformed cell before guarded checks |
| `\copy` / `docker cp` errors | File path, permissions, or container name |

---

## Explicit boundary

- **In scope:** Landing (`schedule_driver_path_staging`), typed truth (`schedule_driver_path`), promotion SQL, loader, DB-side validation, neutral inventory counts.
- **Out of scope (until governance + real data):** `v_operator_driver_path_current`, ECharts/Metabase driver-path charts, predecessor/successor parsing, Python/JS path logic, silent “best guess” ordering.

---

## Related artifacts

| Artifact | Role |
| -------- | ---- |
| `sql/01_schema.sql` | Staging + truth tables, FK, indexes, `v_schedule_driver_path_inventory` |
| `sql/05_insert_driver_path.sql` | Promotion + validation |
| `scripts/load_driver_path_export.py` | CSV → staging → promotion orchestration |
| `scripts/validate_driver_path_load.py` | Read-only post-ingest summary of `schedule_driver_path` |
