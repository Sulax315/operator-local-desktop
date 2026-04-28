# Status Board

## Current State

- Phase: Phase 3 — **COMPLETE**; **Phase 5 — operational workflow value** (PARTIAL); Phase 2 runner remains operational
- Status: ACTIVE

## Completed

- Vision defined
- Architecture defined
- Governance system created
- Phase 1 runtime evidence captured (Ollama + Open WebUI) and Phase 1 gate passing
- Registry compatibility policy documented (`build_control/operator_local/13_REGISTRY_COMPATIBILITY_POLICY.md`)
- Global operator response envelope specified (`build_control/operator_local/14_OPERATOR_RESPONSE_ENVELOPE.md`)
- Authoritative build calibration artifact (`build_control/operator_local/15_BUILD_CALIBRATION.json`)
- **Phase 3 complete:** all inventoried operator-facing Python wrappers emit canonical envelope artifacts; inventory has no `active_unwrapped` entries; `make operator-init-run` classified scaffolding-only (`internal_only`)

## Next Action

**Phase 5 — initial completion bar (locked):** at least **three** weekly-used deterministic workflows, each with registry entry, bounded inputs, stable `structured_output` schema (`schema_version: "1.0"` for operational trio), full artifact set, `init_operator_run` → `run_workflow` → `validate_operator_run` integration test, plus **one ugly-input test per workflow**.

- **Canonical template:** `wf_compare_markdown` — all new Phase 5 operational workflows match this operational pattern unless a documented exception is approved (decision log).
- **In repo now:** `wf_compare_markdown`, hardened `wf_extract_risk_lines`, `wf_financial_markdown_delta` (financial signal lines from unified diff).
- **Evaluation + regression:** `build_control/operator_local/phase5_eval_corpus/` + `phase5_eval_manifest.json` + `scripts/run_phase5_eval_pack.py` + `test_phase5_eval_regression` (gate on heuristic drift).
- **Reject Phase 4 broker work** until eval/regression stays green and the trio is judged credible for weekly-style use (decision log).

## Blockers

- None currently tracked in-repo (environment-specific restrictions may still apply on target machines)
