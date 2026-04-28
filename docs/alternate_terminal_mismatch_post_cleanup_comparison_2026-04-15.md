# Alternate Terminal Mismatch Post-Cleanup Comparison (2026-04-15)

## Scope

- Executed normalization cleanup actions for 11 tasks listed in `normalization_cleanup_targets.csv`.
- Re-ran existing evidence-pack exports without SQL/Python/JS logic changes.
- Diagnostics folder: `diagnostics/path_comparison/alternate_terminal_post_cleanup_20260415T134145Z`

## Cleanup Actions Executed

- For task IDs `43836, 44283, 15995, 15987, 15713, 16088, 15980, 16085, 22765, 26105, 22872`:
  - removed predecessor tokens classified as `missing` or `ambiguous`
  - removed predecessor tokens flagged as `is_self_loop = true`
  - de-duplicated repeated predecessor tokens (kept first ordinal occurrence)
- Rows updated in `schedule_tasks`: **11**

## Baseline vs Post-Cleanup (Authoritative Baseline From Handoff)

| Metric | Baseline (handoff) | Post-cleanup (this run) | Delta |
|---|---:|---:|---:|
| Total mismatch rows | 87 | 13 | -74 |
| Structural bucket | 76 | 13 | -63 |
| Normalization bucket | 11 | 0 | -11 |
| Terminal-selection-policy bucket | 0 | 0 | 0 |

## Runtime Pre vs Post In This Execution

| Metric | Runtime pre-cleanup | Runtime post-cleanup | Delta |
|---|---:|---:|---:|
| Total mismatch rows | 13 | 13 | 0 |
| Structural bucket | 13 | 13 | 0 |
| Normalization bucket | 0 | 0 | 0 |
| Terminal-selection-policy bucket | 0 | 0 | 0 |

## Top Terminal Concentration Before vs After

- Baseline top terminals: 37054, 39146, 45713, 39160, 45708, 37050, 39283, 39297, 41355, 41357
- Post-cleanup top 10 terminals (this run): 37058, 15717, 15965, 15979, 22747, 22767, 23283, 25746, 25747, 25748
- Overlap count: **0/10** (none)
- Presence of prior top-10 terminals in post-cleanup population: each prior terminal still appears in **9 of 13** remaining rows (`top_terminal_signal_matrix.csv`), so the neighborhood remains materially represented despite rank-order tie shifts.
- Concentration ratio (top5 share of top25 occurrences): pre=0.204, post=0.204
- Mismatch population remains concentrated (not diffuse), but around a smaller surviving subset.

## High-Reach Task Dominance Before vs After

- Baseline high-reach tasks: 43882, 52902, 43885, 43888, 43891, 43836
- Post-cleanup top 10 high-reach task IDs: 52902, 43845, 43846, 52929, 52923, 44228, 44229, 44322, 15997, 43388
- Overlap count: **1/6** (52902)

## Determination Inputs

- Relative to handoff baseline, mismatch counts dropped materially (87 -> 13).
- In this execution window, pre/post were stable at 13 -> 13 (indicating collapse already present before cleanup was applied in this run).
- Normalization candidates are 0 after rerun; remaining rows are structural-tagged.