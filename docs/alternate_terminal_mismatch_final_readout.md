# Alternate Terminal Mismatch Final Readout (Authoritative)

## Scope

This readout is restricted to post-cleanup analysis artifacts and does not alter any classification logic or recompute prior runs.

Sources:

- `diagnostics/path_comparison/alternate_terminal_mismatch_20260415T125809Z/bucket_summary_counts.csv`
- `diagnostics/path_comparison/alternate_terminal_post_cleanup_20260415T134145Z/pre_bucket_summary_counts.csv`
- `diagnostics/path_comparison/alternate_terminal_post_cleanup_20260415T134145Z/bucket_summary_counts.csv`

## 3-State Timeline

| State | Total mismatch rows | Structural rows | Normalization rows |
|---|---:|---:|---:|
| Original mismatch baseline | 87 | 76 | 11 |
| Runtime pre-cleanup | 13 | 13 | 0 |
| Runtime post-cleanup | 13 | 13 | 0 |

## Amplification Explanation

- Baseline normalization amplification factor: `76 / 11 = 6.91x` (reported operationally as approximately `6.7x`).
- Interpretation: a relatively small normalization-defect cohort can materially inflate or distort alternate-terminal mismatch interpretation when mixed into structural diagnostics.
- Post-cleanup behavior confirms this: normalization candidates collapsed from 11 to 0, while the 13 structural rows persisted unchanged.

## Corrected Interpretation

**Bounded structural anomaly after normalization collapse.**

What changed:

- Normalization noise was removed from the active mismatch set.
- Residual mismatch set remained stable at 13 structural rows before and after cleanup.

What did not change:

- The structural terminal concentration pattern remains present.
- Alternate finish-chain divergence still exists in a bounded subset of tasks.

## Explicit System Insight

**Normalization defects distort graph-based reasoning.**

When predecessor token quality degrades (missing/ambiguous/invalid references), graph traversal and terminal attribution can over-report or misattribute alternate finish chains. Once normalization defects are removed from the mismatch population, the remaining anomaly is smaller, more stable, and structurally interpretable.
