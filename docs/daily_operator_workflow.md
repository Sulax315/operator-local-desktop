# Daily Operator Workflow

## Purpose
Operationalize the existing productivity loop so field teams can enter daily production in Airtable, load governed rows into PostgreSQL, and review outcomes in Metabase.

## Daily Loop (Concrete)
1. **Define baseline once (or when scope plan changes)**
   - Confirm `scope_baseline` has one governed baseline row per canonical `project_code + scope_code + unit_code`.
   - Required baseline fields: `project_code`, `scope_code`, `unit_code`, `baseline_quantity`, `planned_install_days`, `effective_date`, `source_reference`.
   - Baseline remains authoritative in PostgreSQL.

2. **Enter daily production rows in Airtable**
   - Use the Airtable daily entry table defined in `docs/airtable_daily_entry_setup.md`.
   - Enter one row per scope worked per day with required fields:
     - `work_date`
     - `project_code`
     - `scope_code`
     - `unit_code`
     - `quantity_installed`
     - `entered_by`
     - `notes`
     - `source_record_id`

3. **Export CSV from Airtable**
   - Export the daily table to CSV.
   - Keep headers unchanged and preserve canonical codes exactly.

4. **Load CSV into staging**
   - Ensure staging table exists via `sql/15_production_log_staging.sql`.
   - Import CSV into `stg_production_log_daily_csv` (manual `\copy` path).

5. **Run mandatory pre-load unit gate**
   - Run `sql/12_preload_unit_validation.sql`.
   - Required result: zero violations for:
     - mixed units within a `project_code + scope_code`
     - baseline vs production unit mismatch
   - If any violations are returned, stop and correct source data before loading.

6. **Promote valid rows into `production_log`**
   - Run `sql/16_import_production_log_from_staging.sql`.
   - Script performs required-field checks, controlled casting, and safe insert behavior.

7. **Verify computed outputs**
   - Query `v_scope_baseline`, `v_scope_actual`, and `v_scope_productivity`.
   - Confirm expected baseline, actual productivity, and variance are present.

8. **Review in Metabase**
   - Open the productivity dashboard and review:
     - baseline vs actual
     - variance by scope
     - worst performers
     - trend

## Operator Rules
- Airtable is input only.
- PostgreSQL SQL artifacts remain authoritative for business logic.
- Metabase remains projection only.
- Do not compute authoritative productivity in Airtable formulas or Metabase expressions.
- Do not bypass `sql/12_preload_unit_validation.sql`.

## Recommended Cadence
- **Daily:** enter rows, export, stage, validate, load, verify dashboard.
- **Weekly:** run trend review and confirm no unresolved validation failures.
