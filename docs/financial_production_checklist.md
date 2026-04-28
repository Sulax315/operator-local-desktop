# Financial control loop — production checklist

Use this as the **minimum bar** before calling the workflow “production” for a job or environment. Automation: `scripts/operator_run_financial_cycle.py` and `scripts/apply_financial_sql.sh`.

1. **Pin the truth layer** — Postgres is sole financial semantics; Metabase and `/financial-signals` are projections only (no KPI math in JS beyond assembly).
2. **Apply SQL in canonical order** — `10 → 11 → 13 → 12 → 14` (see `scripts/apply_financial_sql.sh`; loader applies the same chain when not using `--skip-ddl`). Never skip 13 before 12; mitigation depends on change-order classification.
3. **Verify views and registry** — Run `python3 scripts/validate_financial_views.py` (optional `--project-code`). Expect `v_financial_operator_health` and migration row for `14_financial_operator_health`.
4. **Secrets and connectivity** — `.env` has `POSTGRES_*`; Metabase credentials live in a **gitignored** file on the VM (commonly `config/metabase_publish.env`). See `config/README.md` and run `python3 scripts/operator_run_financial_cycle.py show-metabase-env`. No Metabase admin in browser for routine publishes.
5. **Loader discipline** — Every load creates `financial_import_batch` with explicit `load_label`; use `operator_actor` / `operator_notes` when provided (columns from `14_*.sql`). Prefer manifest loads for backfills.
6. **Post-load validation** — Run validation script after each batch; spot-check `v_financial_exec_kpi_latest`, `v_financial_change_order_*`, and `v_financial_data_quality_flags_latest` for the project.
7. **Metabase publish** — `python3 scripts/publish_financial_control_loop_metabase.py --env-file …` after schema or question changes; confirm dashboard filters (`project_code`, `as_of_cost_report_date`) and the change-order card.
8. **Operator UI smoke** — `scripts/smoke.sh` (HTTP + JSON contract). Optionally `SMOKE_FINANCIAL_DB=1` to assert DB views from the host.
9. **Audit trail** — Use `operator_run_financial_cycle.py run` so JSON audits land in `runtime/operator_audit/` (load/publish/validation blocks).
10. **Cadence and ownership** — Document who runs weekly cost/profit refresh, who signs off monthly, and where variance narrative is stored (runbook §5–6 in `docs/financial_control_loop_runbook.md`).
