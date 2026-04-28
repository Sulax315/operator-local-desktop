# Continuity — financial control loop (paste for a new thread)

Copy everything inside the fence below into a new conversation when resuming **financial ingestion, SQL views, Metabase financial dashboard, or `/financial-signals`** work.

```
You are continuing Bratek Operator Stack work on the **financial control loop** (cost/profit → Postgres → views → Metabase + ECharts projection).

Repo: /srv/operator-stack-clean

Authoritative architecture:
- **Postgres views and loaders own financial semantics.** Application code (FastAPI) only assembles read-only JSON for charts; it does not redefine KPIs, variance rules, or mitigation scoring when the SQL view exists.
- **ECharts `/financial-signals`** is projection-only, same rule family as Phase 4 schedule charts: no second truth layer in JS.

SQL apply order (always this sequence; `ON_ERROR_STOP=1`):
1. `sql/financial/10_financial_control_loop_schema.sql` — tables / import batch / raw staging
2. `sql/financial/11_financial_control_loop_views.sql` — typed + latest-batch views + primary operator views
3. `sql/financial/13_financial_change_order_views.sql` — CO classification (`18.*` owner, `21.*` CM contingency) + rollup view
4. `sql/financial/12_financial_mitigation_priority_view.sql` — `v_financial_mitigation_priority_latest` (expects step 3 applied; uses `DROP VIEW IF EXISTS` when column layout changes)
5. `sql/financial/14_financial_operator_health.sql` — `financial_schema_migration`, optional `operator_actor` / `operator_notes` on batches, `v_financial_operator_health`, `v_financial_data_quality_flags_latest`
6. `sql/financial/15_evm_schema.sql` — EVM tables
7. `sql/financial/16_evm_views.sql` — `v_evm_*` views
8. `sql/financial/17_financial_training_signals.sql` — `financial_pm_review_event`, `v_financial_training_signals_latest`, `v_financial_training_signal_portfolio_latest`

Example apply (adjust container user/db if your `.env` differs; run from repo root):

cd /srv/operator-stack-clean
docker exec -i bratek-phase1-postgres psql -U bratek_ops -d postgres -v ON_ERROR_STOP=1 < sql/financial/10_financial_control_loop_schema.sql
docker exec -i bratek-phase1-postgres psql -U bratek_ops -d postgres -v ON_ERROR_STOP=1 < sql/financial/11_financial_control_loop_views.sql
docker exec -i bratek-phase1-postgres psql -U bratek_ops -d postgres -v ON_ERROR_STOP=1 < sql/financial/13_financial_change_order_views.sql
docker exec -i bratek-phase1-postgres psql -U bratek_ops -d postgres -v ON_ERROR_STOP=1 < sql/financial/12_financial_mitigation_priority_view.sql
docker exec -i bratek-phase1-postgres psql -U bratek_ops -d postgres -v ON_ERROR_STOP=1 < sql/financial/14_financial_operator_health.sql
docker exec -i bratek-phase1-postgres psql -U bratek_ops -d postgres -v ON_ERROR_STOP=1 < sql/financial/15_evm_schema.sql
docker exec -i bratek-phase1-postgres psql -U bratek_ops -d postgres -v ON_ERROR_STOP=1 < sql/financial/16_evm_views.sql
docker exec -i bratek-phase1-postgres psql -U bratek_ops -d postgres -v ON_ERROR_STOP=1 < sql/financial/17_financial_training_signals.sql

Primary **operator-facing views** (names to grep / validate in Metabase SQL):
- `v_financial_exec_kpi_latest`
- `v_financial_profit_trend`
- `v_financial_cost_code_variance_latest`
- `v_financial_exception_alerts_latest`
- `v_financial_training_signals_latest`, `v_financial_training_signal_portfolio_latest` (step `17`)
- `v_financial_mitigation_priority_latest` (requires `13` then `12`; see API fallback below)
- `v_financial_cost_line_change_order_class_latest`, `v_financial_cost_rollup_by_change_order_kind_latest` (step `13`)

**Loaders** (Python):
- `scripts/load_financial_report.py` — single cost or profit xlsx
- `scripts/load_financial_manifest.py` — bulk rows from `templates/financial_load_manifest.csv`
- Dependencies: `scripts/requirements-financial.txt` (`pip install -r` before loads)
- First run can apply DDL; thereafter `--skip-ddl` is normal for repeat loads.

**Metabase** (idempotent REST publisher; native SQL questions only):
- Script: `scripts/publish_financial_control_loop_metabase.py`
- Typical run: `python3 scripts/publish_financial_control_loop_metabase.py --env-file config/metabase_publish.env` (VM-local file; gitignored — see `config/README.md`).
- Wrapper auto-discovery: `python3 scripts/operator_run_financial_cycle.py publish` resolves env in order: `METABASE_FINANCIAL_ENV_FILE`, `METABASE_PUBLISH_ENV_FILE`, `config/metabase_publish.financial.env`, `config/metabase_publish.env`, `~/.config/bratek/metabase_publish.env`. Inspect with `show-metabase-env`.
- Env pattern matches other publishers (`config/metabase_publish.env.example`); financial-specific: `METABASE_DATABASE_NAME`, collection, dashboard id/name, `METABASE_DEFAULT_PROJECT_CODE`, optional `METABASE_DEFAULT_AS_OF_COST_REPORT_DATE`.
- Dashboard default name env: `METABASE_FINANCIAL_DASHBOARD_DEFAULT_NAME` (see script/runbook).
- Publisher ensures dashboard parameters `project_code` + `as_of_cost_report_date` and maps them into native SQL template tags (profit-trend card is project-code only).

**Operator ECharts surface:**
- Page: `http://127.0.0.1:8090/financial-signals` (service `operator_echarts`, compose service name `operator_echarts`, image build `web/operator_echarts`)
- API: `GET /api/operator/financial-executive-visuals?project_code=<code>`
  - Default project code: query param, else `OPERATOR_DEFAULT_PROJECT_CODE` env in container, else app default (see `web/operator_echarts/app.py`).

**API payload contract (high-signal fields):**
- `project_code`, `kpi_strip`, `profit_trend.rows`, `cost_code_variance.rows`, `exception_alerts.rows`, `exception_funnel`, `variance_summary`, `category_rollup`, `data_quality`, `exec_brief.lines`, `metadata` (includes `generated_at_utc`, `source_views`, notes).
- **`budget_bridge`**: derived server-side from `kpi_strip` (`v_financial_exec_kpi_latest`) for waterfall-style headroom steps — not a separate SQL view.
- **`mitigation_ranked`**: `{ "rows", "row_cap", "source" }`.
  - **`source`** is normally `"v_financial_mitigation_priority_latest"`.
  - **Fallback**: if the mitigation view is missing (`UndefinedTable`), `source` becomes `"python_fallback_same_formula"` and rows are re-ranked from variance using the same formula as SQL (see `_mitigation_score_python` in `app.py`). **Apply `12_financial_mitigation_priority_view.sql`** so production uses SQL rank, not fallback.
- **`change_orders`**: `{ "classification_rule", "rollup": { rows, source }, "lines": { rows, row_cap, source } }` — owner vs CM contingency vs standard lines from cost_code prefix **18** / **21** (see `13_*.sql`). **`source`** = `views_not_deployed` if step 13 was not applied.
- **`training_signals`**: `{ "rows", "by_severity", "row_cap", "source" }` from `v_financial_training_signals_latest`; portfolio rollup: `GET /api/operator/financial-training-signals-portfolio`. Log reviews with `scripts/record_financial_pm_review.py`.

**Rebuild / redeploy (typical):**
- After changing FastAPI or static assets under `web/operator_echarts/`:
  - `docker compose build operator_echarts && docker compose up -d operator_echarts --no-deps`
- After SQL-only changes: re-run the `psql` trio above; restart Echarts only if you want a clean process (usually not required).
- `scripts/smoke.sh` includes HTTP checks for `/financial-signals` and `/api/operator/financial-executive-visuals` plus JSON paths for `metadata.generated_at_utc`, `budget_bridge.steps`, `mitigation_ranked.source`, `mitigation_ranked.rows`, `change_orders.*`. Set `SMOKE_FINANCIAL_DB=1` to also run `scripts/validate_financial_views.py` against Postgres (default container `bratek-phase1-postgres`).
- Canonical bundle apply: `scripts/apply_financial_sql.sh` or `python3 scripts/operator_run_financial_cycle.py apply-sql` (writes audit JSON). Full production flow: `docs/financial_production_checklist.md`.

**Caveats:**
- Metabase profit-trend card does not apply `as_of_cost_report_date` (view has no such column); use `project_code` and interpret trend as full history unless you add a new SQL view.
- API `metadata.notes`: profit trend can be **provisional** if legacy templates mis-map columns — validate against source xlsx when something looks off.

**Suggested follow-ups:**
- Optional SQL view: profit trend scoped to reporting window (e.g. filter by related cost batch dates) so the dashboard date filter applies consistently.
- Optional: guarded wrapper / audit JSON for `load_financial_manifest.py` + Metabase publish, mirroring `operator_run_snapshot_cycle.py` patterns.
- Phase 4 hardening: auth / TLS for `operator_echarts` when governance requires it.

Long-form procedure: docs/financial_control_loop_runbook.md
Schedule-stack continuity (separate): docs/CONTINUITY_FOR_NEW_THREAD.md
```

Long-form runbook: **`docs/financial_control_loop_runbook.md`**.
