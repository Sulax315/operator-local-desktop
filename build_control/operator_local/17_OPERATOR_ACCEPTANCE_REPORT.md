# Phase 6 Operator Acceptance Report

Date: 2026-04-21

Runs executed: 9 (3 compare, 3 risk, 3 financial)

## Case 1 — `wf_compare_markdown`
- Command: `./operator compare build_control/operator_local/phase5_eval_corpus/compare/c01_left.md build_control/operator_local/phase5_eval_corpus/compare/c01_right.md`
- Run ID: `run_20260421_170425_7276df`
- Verdict: **ready**
- Summary:
  - Changed line count: 2
  - Changed heading lines: 0
  - Significance tier: SMALL
- What to review:
  - Review changed headings/sections first to confirm structural impact.
  - Confirm significance tier matches actual operational importance of the edits.
- Output path: `/srv/operator-stack-clean/runs/run_20260421_170425_7276df/outputs`

## Case 2 — `wf_compare_markdown`
- Command: `./operator compare build_control/operator_local/phase5_eval_corpus/compare/c04_left.md build_control/operator_local/phase5_eval_corpus/compare/c04_right.md`
- Run ID: `run_20260421_170425_c375c6`
- Verdict: **ready**
- Summary:
  - Changed line count: 4
  - Changed heading lines: 1
  - Significance tier: SMALL
- What to review:
  - Review changed headings/sections first to confirm structural impact.
  - Confirm significance tier matches actual operational importance of the edits.
- Output path: `/srv/operator-stack-clean/runs/run_20260421_170425_c375c6/outputs`

## Case 3 — `wf_compare_markdown`
- Command: `./operator compare build_control/operator_local/phase5_eval_corpus/compare/c05_left.md build_control/operator_local/phase5_eval_corpus/compare/c05_right.md`
- Run ID: `run_20260421_170425_2e0a64`
- Verdict: **ready**
- Summary:
  - Changed line count: 2
  - Changed heading lines: 0
  - Significance tier: SMALL
- What to review:
  - Review changed headings/sections first to confirm structural impact.
  - Confirm significance tier matches actual operational importance of the edits.
- Output path: `/srv/operator-stack-clean/runs/run_20260421_170425_2e0a64/outputs`

## Case 4 — `wf_extract_risk_lines`
- Command: `./operator risk build_control/operator_local/phase5_eval_corpus/risk/r01_weekly_notes.md`
- Run ID: `run_20260421_170426_9c84c8`
- Verdict: **ready_with_caveats**
- Summary:
  - Action-needed items: 1
  - Informational items: 1
  - Truncated output: NO
- What to review:
  - Review action-needed items first for immediate mitigation/escalation decisions.
  - Scan informational items only when context is sensitive or deadlines are near.
- Output path: `/srv/operator-stack-clean/runs/run_20260421_170426_9c84c8/outputs`

## Case 5 — `wf_extract_risk_lines`
- Command: `./operator risk build_control/operator_local/phase5_eval_corpus/risk/r03_one_substantive.md`
- Run ID: `run_20260421_170426_e1c944`
- Verdict: **ready_with_caveats**
- Summary:
  - Action-needed items: 1
  - Informational items: 0
  - Truncated output: NO
- What to review:
  - Review action-needed items first for immediate mitigation/escalation decisions.
  - Scan informational items only when context is sensitive or deadlines are near.
- Output path: `/srv/operator-stack-clean/runs/run_20260421_170426_e1c944/outputs`

## Case 6 — `wf_extract_risk_lines`
- Command: `./operator risk build_control/operator_local/phase5_eval_corpus/risk/r05_actions.md`
- Run ID: `run_20260421_170426_3cc98e`
- Verdict: **ready_with_caveats**
- Summary:
  - Action-needed items: 2
  - Informational items: 2
  - Truncated output: NO
- What to review:
  - Review action-needed items first for immediate mitigation/escalation decisions.
  - Scan informational items only when context is sensitive or deadlines are near.
- Output path: `/srv/operator-stack-clean/runs/run_20260421_170426_3cc98e/outputs`

## Case 7 — `wf_financial_markdown_delta`
- Command: `./operator financial build_control/operator_local/phase5_eval_corpus/financial/f01_prior.md build_control/operator_local/phase5_eval_corpus/financial/f01_current.md`
- Run ID: `run_20260421_170426_2a5c4a`
- Verdict: **ready_with_caveats**
- Summary:
  - Primary material items: 2
  - Audit-only items: 0
  - High-confidence primary exists: YES
- What to review:
  - Review primary material items first; treat these as claim-level changes.
  - Use audit-only items for completeness checks, not as primary decision signal.
- Output path: `/srv/operator-stack-clean/runs/run_20260421_170426_2a5c4a/outputs`

## Case 8 — `wf_financial_markdown_delta`
- Command: `./operator financial build_control/operator_local/phase5_eval_corpus/financial/f04_prior.md build_control/operator_local/phase5_eval_corpus/financial/f04_current.md`
- Run ID: `run_20260421_170427_cecec8`
- Verdict: **ready_with_caveats**
- Summary:
  - Primary material items: 2
  - Audit-only items: 0
  - High-confidence primary exists: YES
- What to review:
  - Review primary material items first; treat these as claim-level changes.
  - Use audit-only items for completeness checks, not as primary decision signal.
- Output path: `/srv/operator-stack-clean/runs/run_20260421_170427_cecec8/outputs`

## Case 9 — `wf_financial_markdown_delta`
- Command: `./operator financial build_control/operator_local/phase5_eval_corpus/financial/f06_prior.md build_control/operator_local/phase5_eval_corpus/financial/f06_current.md`
- Run ID: `run_20260421_170427_16a366`
- Verdict: **ready_with_caveats**
- Summary:
  - Primary material items: 0
  - Audit-only items: 2
  - High-confidence primary exists: NO
- What to review:
  - Review primary material items first; treat these as claim-level changes.
  - Use audit-only items for completeness checks, not as primary decision signal.
- Output path: `/srv/operator-stack-clean/runs/run_20260421_170427_16a366/outputs`

## Overall

- `wf_compare_markdown`: **ready** (specific summary + targeted review guidance are immediately actionable).
- `wf_extract_risk_lines`: **ready_with_caveats** (actionable-first guidance helps; informational noise still requires operator judgment).
- `wf_financial_markdown_delta`: **ready_with_caveats** (primary/audit split is useful; audit remains contextual completeness layer).
