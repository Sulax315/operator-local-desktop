# Financial Control Loop Runbook (Python + Postgres + Metabase)

## Purpose
Create a repeatable financial workflow per job so every cost/profit update follows the same ingestion, KPI, and exception-monitoring process.

## Components
- Loader: `scripts/load_financial_report.py`
- SQL schema: `sql/financial/10_financial_control_loop_schema.sql`
- SQL views: `sql/financial/11_financial_control_loop_views.sql`, `sql/financial/13_financial_change_order_views.sql`, `sql/financial/12_financial_mitigation_priority_view.sql`, `sql/financial/14_financial_operator_health.sql` (apply **13 before 12**; **14** last — migration registry, batch provenance columns, health/DQ views)
- Production checklist: **`docs/financial_production_checklist.md`**
- Guarded cycle + audit JSON: **`scripts/operator_run_financial_cycle.py`** (subcommands: `preflight`, `apply-sql`, `validate`, `publish`, `load-manifest`, `run`)
- One-shot SQL apply: **`scripts/apply_financial_sql.sh`**
- Metabase publisher: `scripts/publish_financial_control_loop_metabase.py`
- Python deps: `scripts/requirements-financial.txt`

## 1) One-time setup

Install loader dependencies:

```bash
python3 -m pip install -r scripts/requirements-financial.txt
```

Apply schema/views once (the loader can also do this automatically on first run):

```bash
docker exec -i bratek-phase1-postgres psql -U bratek_ops -d postgres -v ON_ERROR_STOP=1 < sql/financial/10_financial_control_loop_schema.sql
docker exec -i bratek-phase1-postgres psql -U bratek_ops -d postgres -v ON_ERROR_STOP=1 < sql/financial/11_financial_control_loop_views.sql
docker exec -i bratek-phase1-postgres psql -U bratek_ops -d postgres -v ON_ERROR_STOP=1 < sql/financial/13_financial_change_order_views.sql
docker exec -i bratek-phase1-postgres psql -U bratek_ops -d postgres -v ON_ERROR_STOP=1 < sql/financial/12_financial_mitigation_priority_view.sql
docker exec -i bratek-phase1-postgres psql -U bratek_ops -d postgres -v ON_ERROR_STOP=1 < sql/financial/14_financial_operator_health.sql
```

## 2) Load each new report file

### Cost report
```bash
python3 scripts/load_financial_report.py \
  --report-type cost \
  --project-code 219128 \
  --report-date 2026-03-25 \
  --file-path "/path/to/219128 Cost Report Update_12.11.2025.xlsx"
```

### Profit report
```bash
python3 scripts/load_financial_report.py \
  --report-type profit \
  --project-code 219128 \
  --report-date 2026-03-25 \
  --file-path "/path/to/219128 Profit Report Update_2026-03-25 (1).xlsx"
```

Notes:
- `--report-date` should reflect the reporting period date you want to track.
- Use `--sheet "Sheet Name"` if data is not in the default first sheet.
- Use `--skip-ddl` after your first successful run to avoid reapplying schema/views each time.

### Bulk load from manifest

Use `templates/financial_load_manifest.csv` as the starting format, then run:

```bash
python3 scripts/load_financial_manifest.py \
  --manifest-path templates/financial_load_manifest.csv
```

`templates/financial_load_manifest.csv` is pre-populated with your provided `219128` report set, sorted by `report_date`, with explicit `load_label` values for audit-safe reruns.

For large backfills where you want to continue through bad rows:

```bash
python3 scripts/load_financial_manifest.py \
  --manifest-path templates/financial_load_manifest.csv \
  --skip-ddl \
  --continue-on-error
```

### Preflight file-path check (recommended before load)

```bash
python3 scripts/load_financial_manifest.py \
  --manifest-path templates/financial_load_manifest.csv \
  --preflight-only
```

This prints `OK`/`MISSING` per row and the resolved path used by the loader.

## Where to run these commands

- Use a terminal where this repo is accessible at `/srv/operator-stack-clean`.
- If you are in Windows:
  - **PowerShell is fine** if Python and Docker are available there, and if paths in the manifest are reachable from that shell.
  - **WSL terminal is also fine**; loader supports Windows-style `C:\...` paths and attempts to resolve them to Linux mount paths automatically.
- Always run commands from the repo root:

```bash
cd /srv/operator-stack-clean
```

## 3) Validate latest project outputs

Run in Postgres:

```sql
SELECT * FROM v_financial_exec_kpi_latest WHERE project_code = '219128';
SELECT * FROM v_financial_profit_trend WHERE project_code = '219128' ORDER BY profit_month;
SELECT * FROM v_financial_exception_alerts_latest WHERE project_code = '219128';
SELECT * FROM v_financial_cost_code_variance_latest WHERE project_code = '219128' LIMIT 100;
```

## 4) Metabase model wiring

Use the Metabase REST publisher (idempotent: upserts questions, wires tiles, avoids duplicate cards):

```bash
python3 scripts/publish_financial_control_loop_metabase.py --env-file config/metabase_publish.env
# Or use the wrapper (auto-finds config/metabase_publish.env on this VM when present):
#   python3 scripts/operator_run_financial_cycle.py show-metabase-env
#   python3 scripts/operator_run_financial_cycle.py publish --dry-run
```

Env requirements match `config/metabase_publish.env.example` (same variables as the other publishers), plus these financial-specific knobs:

- `METABASE_DATABASE_NAME`: must match the friendly database name in Metabase (example: `Operator Postgres (Financial)`).
- `METABASE_COLLECTION_NAME`: collection that will hold the saved questions (created at root if missing).
- Dashboard selection:
  - If `METABASE_DASHBOARD_ID` is set, that dashboard is updated in-place.
  - Else if `METABASE_DASHBOARD_NAME` is set, that exact-name dashboard is reused if it exists; otherwise it is created.
  - Else a new dashboard is created using `METABASE_FINANCIAL_DASHBOARD_DEFAULT_NAME` (default: `Project Financial Control Loop - v1`).
- `METABASE_DEFAULT_PROJECT_CODE` (optional): default for the native SQL variable `{{project_code}}` and the dashboard filter default (default: `219128`).
- `METABASE_DEFAULT_AS_OF_COST_REPORT_DATE` (optional): default for the dashboard date filter and native SQL variable `{{as_of_cost_report_date}}` (ISO `YYYY-MM-DD`). Omit for an unset optional filter.

The dashboard is backed by saved questions querying:
- `v_financial_exec_kpi_latest` (KPI strip)
- `v_financial_profit_trend` (trend chart)
- `v_financial_cost_code_variance_latest` (risk table)
- `v_financial_mitigation_priority_latest` (mitigation-ranked table; includes `change_order_kind` / `is_change_order_line` when views 13+12 are applied)
- `v_financial_exception_alerts_latest` (exception table)
- `v_financial_cost_rollup_by_change_order_kind_latest` (change-order vs standard-line dollars — **18.\*** owner CO, **21.\*** CM contingency CO)
- `v_financial_operator_health` (single-row readiness: import counts, critical view flags)
- `v_financial_data_quality_flags_latest` (per-project raw-line DQ on latest cost batch)

Dashboard filters (created/updated by the publisher):
- `project_code` (required) — wired to every card.
- `as_of_cost_report_date` (optional) — wired to every card **except** the profit trend chart (`v_financial_profit_trend` has no cost as-of column; that card follows `project_code` only). Other questions use native SQL `[[AND as_of_cost_report_date = {{as_of_cost_report_date}}]]` so the clause drops out when the filter is empty.

## 5) Operating cadence

- Weekly: load newest cost/profit files for active jobs.
- Monthly close: confirm KPI snapshot for each active project and review exceptions.
- Handoff packet: export the dashboard + a short variance narrative (top 3 downward movers and mitigation actions).

## 6) Expected behavior and safeguards

- Every file load creates a `financial_import_batch` row with `batch_id`, file path, and load label.
- Raw rows remain preserved for auditability.
- Typed views normalize currency/percent strings into numerics.
- Latest views always resolve to most recent cost batch and profit month per project.

## 7) Common issues

- **Missing columns on load:** column names differ from expected aliases. Adjust headers in source file or extend aliases in `scripts/load_financial_report.py`.
- **Batch insert fails on `operator_actor` / `operator_notes`:** apply `sql/financial/14_financial_operator_health.sql` (or run `scripts/apply_financial_sql.sh`) so `financial_import_batch` has the new columns.
- **xlsx read error:** install `openpyxl` (`python3 -m pip install openpyxl`).
- **DB connection failure in docker mode:** verify container name (`bratek-phase1-postgres`) and credentials from `.env`.
