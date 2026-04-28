# Workflow Contract Lock (Phase 6)

## Locked workflows

- `wf_compare_markdown`
  - `schema_version`: `1.0`
  - required artifacts: `outputs/structured_report.md`, `outputs/structured_output.json`, `outputs/runner.json`, `outputs/diff.unified.diff`, envelope artifacts
- `wf_extract_risk_lines`
  - `schema_version`: `1.0`
  - required artifacts: `outputs/structured_report.md`, `outputs/structured_output.json`, `outputs/runner.json`, envelope artifacts
- `wf_financial_markdown_delta`
  - `schema_version`: `1.0`
  - `signal_pattern_id`: `financial_markdown_v3`
  - required artifacts: `outputs/structured_report.md`, `outputs/structured_output.json`, `outputs/runner.json`, `outputs/diff.unified.diff`, envelope artifacts

## Change policy

Any contract change must do all of:

1. Bump workflow contract indicator (`schema_version` and/or signal/rules ID).
2. Update `build_control/operator_local/09_WORKFLOW_REGISTRY.json` if required outputs change.
3. Update tests and regression manifests.
4. Pass `scripts/run_full_regression.py`.

No silent contract drift.
