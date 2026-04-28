# Operator Daily Checklist

Use this before closing each daily productivity cycle.

- [ ] Did I enter today's quantities for each worked scope in Airtable?
- [ ] Did each row use the governed `unit_code` for that `project_code + scope_code`?
- [ ] Did `sql/12_preload_unit_validation.sql` return zero rows for violations?
- [ ] Did `sql/16_import_production_log_from_staging.sql` complete successfully?
- [ ] Did Metabase reflect expected baseline vs actual movement and variance?

If any item fails, stop publish/review and correct the intake data first.
