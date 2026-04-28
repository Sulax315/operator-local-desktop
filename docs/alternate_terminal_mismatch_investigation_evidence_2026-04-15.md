# Alternate Terminal Mismatch Investigation Evidence (2026-04-15)

## Scope

Executed the SQL snippets in `docs/echarts_path_comparison_runbook.md` against
`v_operator_path_comp_alt_terminal_mismatch_diag_current` without changing any logic.

Raw exports are in:
`diagnostics/path_comparison/alternate_terminal_mismatch_20260415T125809Z`

## Query Outputs Collected

- Bucket exports by `operator_action_signal`:
  - `bucket_dependency_normalization_issue_candidate.csv`
  - `bucket_terminal_selection_policy_issue_candidate.csv`
  - `bucket_true_alternate_finish_chain_structure_candidate.csv`
- Top alternate terminal IDs:
  - `top_alternate_terminal_ids.csv`
- Top rows by `reachable_alternate_terminal_count`:
  - `top_rows_by_reachable_alternate_terminal_count.csv`
- Bucket counts:
  - `bucket_summary_counts.csv`
- Normalization-bucket terminal concentration:
  - `top_alternate_terminal_ids_normalization_bucket.csv`

## Key Findings

- Total mismatch rows: `87`
- Bucket split:
  - `dependency_normalization_issue_candidate`: `11` (12.6%)
  - `true_alternate_finish_chain_structure_candidate`: `76` (87.4%)
  - `terminal_selection_policy_issue_candidate`: `0`
- Dominant alternate terminal IDs by frequency:
  - `37054` (83), `39146` (83), `45713` (83), `39160` (80), `45708` (78)
  - followed by `37050` (77), `39283` (77), `39297` (77), `41355` (76), `41357` (76)
- Highest-priority task rows by alternate reachability are concentrated in:
  - `Array Lower Tiebacks` (`52902`)
  - `Form Foundations` East/North sequences (`43882`, `43885`, `43888`, `43891`, `43836`, ...)

## Structure Assessment

- Pattern is concentrated rather than diffuse: the same alternate terminal IDs recur across most rows.
- Normalization candidates overlap with the same terminal neighborhood as structural candidates, so cleanup and structure validation should run in parallel on the same terminal set.

## Recommended First Schedule-Review Target Set

Start with terminals:
`37054`, `39146`, `45713`, `39160`, `45708`, `37050`, `39283`, `39297`, `41355`, `41357`.

Then:
- clear the 11 normalization candidates (dependency-quality issues),
- re-check whether the 76 structural candidates remain stable on the same terminal set.
