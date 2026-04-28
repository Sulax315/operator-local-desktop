# Operator Local v1.0.0-rc1 Release Criteria

## Release gate

A release candidate is valid only when all criteria below are true:

1. CLI commands work end-to-end:
   - `./operator compare <left> <right>`
   - `./operator risk <notes>`
   - `./operator financial <prior> <current>`
2. Workflow-specific envelope summaries and review guidance are present for all three workflows.
3. Run contract validation passes (`validate_operator_run.py`) and required artifacts are present.
4. Full regression gate is green:
   - `python3 scripts/run_full_regression.py`
5. Operator acceptance report exists with 9 runs (3 compare, 3 risk, 3 financial):
   - `build_control/operator_local/17_OPERATOR_ACCEPTANCE_REPORT.md`
6. Scope freeze holds:
   - no new workflows
   - no broker work
   - no UI work
   - no unapproved schema expansion

## Discipline rule

No release candidate promotion, no production candidate merge, and no version bump unless `scripts/run_full_regression.py` passes.

## RC tagging procedure

When all criteria are met and approved:

1. Ensure working tree is clean.
2. Tag:
   - `git tag -a v1.0.0-rc1 -m "Operator Local v1.0.0-rc1"`
3. Record tag + commit hash in release notes.
