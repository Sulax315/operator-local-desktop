# Operator Local Runbook

## One-command usage

Preferred from repo root:

- `./operator compare a.md b.md`
- `./operator risk notes.md`
- `./operator financial old.md new.md`

Make wrapper:

- `make operator CMD='compare a.md b.md'`
- `make operator CMD='risk notes.md'`
- `make operator CMD='financial old.md new.md'`

Direct Python (equivalent):

- `python3 scripts/operator_run.py compare a.md b.md`
- `python3 scripts/operator_run.py risk notes.md`
- `python3 scripts/operator_run.py financial old.md new.md`

Optional flags:

- `--runs-root /path/to/runs`
- `--registry /path/to/09_WORKFLOW_REGISTRY.json`

## Input expectations

- `compare`: two markdown/text files in left/right order.
- `risk`: one markdown/text notes file.
- `financial`: two markdown/text files in prior/current order.

## Terminal output format

Each command prints:

- `=== OPERATOR RUN ===`
- workflow + run id
- `--- SUMMARY ---` (from envelope `what_i_found`)
- `--- WHAT TO REVIEW ---` (from envelope `what_needs_review`)
- `--- OUTPUT PATH ---` (`runs/<id>/outputs`)

## Artifact contract

Every successful run contains:

- `manifest.json`
- `operator_summary.md`
- `logs/execution_trace.md`
- `outputs/operator_envelope.json`
- `outputs/operator_envelope.md`
- workflow artifacts required by `build_control/operator_local/09_WORKFLOW_REGISTRY.json`

## Failure handling

If command fails:

1. Read error printed by CLI (fails loudly with subprocess stdout/stderr).
2. Inspect `runs/<id>/outputs/runner.json` when present.
3. Re-run with corrected input files.

Validate any run explicitly:

- `python3 scripts/validate_operator_run.py --run-dir runs/<id>`

## Regression / CI gate

Run full gate locally:

- `python3 scripts/run_full_regression.py`

This runs:

- unit tests
- eval pack (`run_phase5_eval_pack.py`)
- financial FN audit (`run_phase5_financial_fn_audit.py`)
- CLI smoke tests
