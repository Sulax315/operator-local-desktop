# Operator Local v1.0.0-rc1 Readiness Checklist

Date: 2026-04-21
Candidate commit: `864905f`

## Gate status

- [x] CLI command surface works end-to-end:
  - `./operator compare <left> <right>`
  - `./operator risk <notes>`
  - `./operator financial <prior> <current>`
- [x] Workflow-specific envelope summaries + review guidance present for all three workflows.
- [x] Run contract is validated (`validate_operator_run.py`) and required artifacts are enforced by tests.
- [x] Full regression gate passes (`python3 scripts/run_full_regression.py`).
- [x] Operator acceptance evidence exists (9 runs): `build_control/operator_local/17_OPERATOR_ACCEPTANCE_REPORT.md`.
- [x] Scope freeze constraints are documented (no new workflows/broker/UI during closeout).
- [ ] Working tree is clean for RC tag application.

## Known caveats (explicit)

- `wf_extract_risk_lines`: ready with caveats (informational noise still requires operator judgment).
- `wf_financial_markdown_delta`: ready with caveats (audit queue remains contextual completeness layer).

## Supported command surface

- `./operator compare <left> <right>`
- `./operator risk <notes>`
- `./operator financial <prior> <current>`
- `make operator CMD='compare a.md b.md'` (and equivalent risk/financial invocations)

## Decision

Release-candidate behavior is **ready for controlled operator use**, but **not tag-ready** until working tree is clean and the release candidate state is committed.
