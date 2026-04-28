# Remaining Structural Analysis (2026-04-15)

## Method

Primary source:

- `diagnostics/path_comparison/alternate_terminal_post_cleanup_20260415T134145Z/bucket_true_alternate_finish_chain_structure_candidate.csv`

Supporting concentration sources:

- `diagnostics/path_comparison/alternate_terminal_post_cleanup_20260415T134145Z/top_terminal_signal_matrix.csv`
- `diagnostics/path_comparison/alternate_terminal_post_cleanup_20260415T134145Z/top_rows_by_reachable_alternate_terminal_count.csv`

Classification policy applied to each of the 13 rows:

- `true parallel terminal structure`: large reachable alternate-terminal set and in dominant 9-row concentration.
- `missing convergence`: single-terminal branch that appears not to reconverge to selected finish chain.
- `improper terminal assignment`: single-terminal branch indicates likely terminal choice inconsistency.
- `ambiguous logic chain`: sparse/single-terminal branch where intent cannot be determined deterministically from available structure alone.

## Row-Level Classification

| task_id | terminal_id | cause_classification | rationale |
|---:|---|---|---|
| 52902 | dominant cluster (`37050,37054,39146,39160,39283,39297,41355,41357,45708,45713`) | true parallel terminal structure | High alternate-terminal reach (`123`) with full top-cluster overlap. |
| 43845 | dominant cluster (`37050,37054,39146,39160,39283,39297,41355,41357,45708,45713`) | true parallel terminal structure | High reach (`112`) and full top-cluster overlap. |
| 43846 | dominant cluster (`37050,37054,39146,39160,39283,39297,41355,41357,45708,45713`) | true parallel terminal structure | High reach (`112`) and full top-cluster overlap. |
| 52929 | dominant cluster (`37050,37054,39146,39160,39283,39297,41355,41357,45708,45713`) | true parallel terminal structure | High reach (`112`) and full top-cluster overlap. |
| 52923 | dominant cluster (`37050,37054,39146,39160,39283,39297,41355,41357,45708,45713`) | true parallel terminal structure | High reach (`112`) and full top-cluster overlap. |
| 44228 | dominant cluster (`37050,37054,39146,39160,39283,39297,41355,41357,45708,45713`) | true parallel terminal structure | High reach (`112`) and full top-cluster overlap. |
| 44229 | dominant cluster (`37050,37054,39146,39160,39283,39297,41355,41357,45708,45713`) | true parallel terminal structure | High reach (`112`) and full top-cluster overlap. |
| 44322 | dominant cluster (`37050,37054,39146,39160,39283,39297,41355,41357,45708,45713`) | true parallel terminal structure | High reach (`108`) and full top-cluster overlap. |
| 15997 | dominant cluster (`37050,37054,39146,39160,39283,39297,41355,41357,45708,45713`) | true parallel terminal structure | High reach (`105`) and full top-cluster overlap. |
| 43388 | 37058 | ambiguous logic chain | Single alternate terminal with sparse branch signature; structural intent is non-deterministic from current evidence. |
| 45487 | 45502 | missing convergence | Single alternate terminal branch in submittal chain does not converge to selected finish target. |
| 45501 | 45502 | missing convergence | Same terminal and branch family as task `45487`; indicates unresolved convergence pattern. |
| 45503 | 45504 | improper terminal assignment | Parallel submittal-review motif but mapped to a distinct singleton terminal, suggesting terminal attribution inconsistency. |

## Summary

- Total analyzed structural rows: **13**
- Concentrated dominant-cluster structural rows: **9/13**
- Edge-case singleton rows: **4/13**
  - `missing convergence`: **2**
  - `improper terminal assignment`: **1**
  - `ambiguous logic chain`: **1**

Operationally, the dominant behavior is still genuine alternate-finish structural branching, while the remaining single-terminal cases are best treated as targeted logic/assignment follow-up candidates.
