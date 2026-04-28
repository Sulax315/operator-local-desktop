# Productivity Loop Validation Runbook

## Purpose
Apply the initial schema and views, load a controlled sample, and validate baseline/actual/variance computations.

## Preconditions
- PostgreSQL is reachable.
- You have a valid connection string in `DATABASE_URL`.
- Execute commands from repo root.

## Daily Operational Sequence (Airtable -> Postgres -> Metabase)
1. Export current daily rows from Airtable using the table contract in `docs/airtable_daily_entry_setup.md`.
2. Ensure staging/import SQL is applied:
   - `sql/15_production_log_staging.sql`
   - `sql/16_import_production_log_from_staging.sql`
3. Import CSV rows into staging table:
   ```bash
   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
   \copy stg_production_log_daily_csv (
       work_date,
       project_code,
       scope_code,
       unit_code,
       quantity_installed,
       entered_by,
       notes,
       source_record_id
   ) FROM '/absolute/path/to/airtable_export.csv' WITH (FORMAT csv, HEADER true);
   SQL
   ```
4. Run mandatory pre-load gate:
   ```bash
   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/12_preload_unit_validation.sql
   ```
5. If and only if the gate returns zero violations, promote staging rows:
   ```bash
   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/16_import_production_log_from_staging.sql
   ```
6. Query views to verify results:
   - `v_scope_baseline`
   - `v_scope_actual`
   - `v_scope_productivity`
7. Open Metabase and confirm dashboard values match expected daily updates.

## 1) Apply Schema SQL
```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/10_scope_productivity_schema.sql
```

## 2) Apply View SQL
```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/11_scope_productivity_views.sql
```

## 3) Pre-Load Unit Validation (Mandatory)
Run the mixed-unit pre-check before authoritative load/reporting:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/12_preload_unit_validation.sql
```

Expected result for compliant intake:
- First result set (mixed units in production/staging): `0 rows`
- Second result set (baseline vs production unit mismatch): `0 rows`

Operator rule if any rows are returned:
1. Reject authoritative load/reporting for affected `project_code + scope_code`.
2. Classify as **input contract violation**.
3. Correct source rows and re-run `sql/12_preload_unit_validation.sql` until zero violations.

Operator rule if zero rows are returned:
1. Run `sql/16_import_production_log_from_staging.sql`.
2. Verify inserts with:
   ```sql
   SELECT
       project_code,
       scope_code,
       unit_code,
       work_date,
       installed_quantity,
       source_reference
   FROM production_log
   ORDER BY work_date DESC, project_code, scope_code
   LIMIT 50;
   ```

## 4) Load Controlled Sample Data
Use one project and one scope (`cold_formed_metal_framing`) with one unit (`lf`).

```sql
INSERT INTO scope_baseline (
    project_code,
    scope_code,
    unit_code,
    baseline_quantity,
    planned_install_days,
    effective_date,
    source_system,
    source_reference
) VALUES (
    'PRJ-001',
    'cold_formed_metal_framing',
    'lf',
    1000.000,
    10.00,
    DATE '2026-04-01',
    'manual_airtable_export',
    'airtable_export_2026_04_14'
);

INSERT INTO production_log (
    project_code,
    scope_code,
    unit_code,
    work_date,
    installed_quantity,
    source_system,
    source_reference,
    entry_user
) VALUES
    ('PRJ-001', 'cold_formed_metal_framing', 'lf', DATE '2026-04-10', 120.000, 'manual_airtable_export', 'field_row_001', 'superintendent_a'),
    ('PRJ-001', 'cold_formed_metal_framing', 'lf', DATE '2026-04-11', 140.000, 'manual_airtable_export', 'field_row_002', 'superintendent_a'),
    ('PRJ-001', 'cold_formed_metal_framing', 'lf', DATE '2026-04-12', 130.000, 'manual_airtable_export', 'field_row_003', 'superintendent_a');
```

Execute inserts:
```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
-- paste sample INSERT statements here
SQL
```

## 5) Validation Queries
```sql
SELECT project_code, scope_code, baseline_quantity, planned_install_days, baseline_productivity
FROM v_scope_baseline
WHERE project_code = 'PRJ-001'
  AND scope_code = 'cold_formed_metal_framing';

SELECT project_code, scope_code, total_installed_quantity, actual_work_days, actual_productivity
FROM v_scope_actual
WHERE project_code = 'PRJ-001'
  AND scope_code = 'cold_formed_metal_framing';

SELECT
    project_code,
    scope_code,
    baseline_productivity,
    actual_productivity,
    productivity_variance
FROM v_scope_productivity
WHERE project_code = 'PRJ-001'
  AND scope_code = 'cold_formed_metal_framing';
```

Execute:
```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
SELECT project_code, scope_code, baseline_quantity, planned_install_days, baseline_productivity
FROM v_scope_baseline
WHERE project_code = 'PRJ-001'
  AND scope_code = 'cold_formed_metal_framing';

SELECT project_code, scope_code, total_installed_quantity, actual_work_days, actual_productivity
FROM v_scope_actual
WHERE project_code = 'PRJ-001'
  AND scope_code = 'cold_formed_metal_framing';

SELECT
    project_code,
    scope_code,
    baseline_productivity,
    actual_productivity,
    productivity_variance
FROM v_scope_productivity
WHERE project_code = 'PRJ-001'
  AND scope_code = 'cold_formed_metal_framing';
SQL
```

## 6) Expected Output Shape
For the sample data above:
- Baseline productivity: `1000 / 10 = 100`
- Actual productivity: `(120 + 140 + 130) / 3 = 130`
- Variance: `(130 - 100) / 100 = 0.30`

Expected result columns:
- `v_scope_baseline`: `project_code`, `scope_code`, `baseline_quantity`, `planned_install_days`, `baseline_productivity`
- `v_scope_actual`: `project_code`, `scope_code`, `total_installed_quantity`, `actual_work_days`, `actual_productivity`
- `v_scope_productivity`: `project_code`, `scope_code`, `baseline_productivity`, `actual_productivity`, `productivity_variance`

## Common Failure Modes
1. **Connection/auth failure**
   - Symptom: `psql: error: connection to server failed`
   - Fix: verify `DATABASE_URL` and DB availability.

2. **Schema not applied before views**
   - Symptom: `relation "scope_baseline" does not exist`
   - Fix: run `sql/10_scope_productivity_schema.sql` first.

3. **Duplicate sample load**
   - Symptom: unique constraint violation on baseline or production row
   - Fix: delete sample rows for `PRJ-001` and re-run inserts.

4. **Unexpected NULL productivity**
   - Symptom: productivity columns are `NULL`
   - Fix: check `planned_install_days > 0` and that production has at least one distinct `work_date`.

5. **Mixed-unit violation**
   - Symptom: `sql/12_preload_unit_validation.sql` returns rows for `project_code + scope_code`.
   - Fix: reject authoritative load, correct unit assignments to a single governed physical `unit_code`, and rerun pre-load validation.
