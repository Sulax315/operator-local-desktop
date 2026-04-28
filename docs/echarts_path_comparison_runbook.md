# ECharts - Path Comparison Runbook

## Purpose

Operator-facing comparison of current-snapshot membership between:

- Critical Path surface dataset (`v_operator_critical_path_current`)
- Computed Path (v1) dataset (`v_operator_driver_path_computed_current`)

This is projection-only. Postgres remains truth and comparison semantics are computed in SQL, not JS/Python.

## Endpoint and route

- API: `GET /api/operator/path-comparison-current`
- Page: `GET /path-comparison`

## Source SQL dataset/view

- Comparison view: `v_operator_path_comparison_current` (defined in `sql/04_signals.sql`)
- Supporting context views:
  - `v_schedule_snapshot_pair_latest`
  - `v_operator_critical_path_current`
  - `v_operator_driver_path_computed_current`
  - `v_schedule_driver_path_computed_inventory` (metadata only, for algorithm version context)

## Semantics

For each task in the union of critical-path and computed-path current-snapshot task IDs:

- `in_critical_path = true` and `in_computed_path = true` -> `comparison_class = both`
- `in_critical_path = true` and `in_computed_path = false` -> `comparison_class = critical_only`
- `in_critical_path = false` and `in_computed_path = true` -> `comparison_class = computed_only`

Sequence fields:

- `critical_path_sequence` comes from SQL `strip_sequence` when available.
- `computed_path_sequence` comes from SQL `path_sequence` when available.
- If a source has no sequence for a row, the sequence is `null` and rendered as such.

## Required warning language

The page/API warning text must remain explicit:

`Computed path is SQL-computed from normalized dependencies and is not engine-authoritative Asta driving path.`

Do not relabel computed output as authoritative truth.

## Quick validation steps

From repo root, with API running on loopback:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/path-comparison
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/critical-path
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/computed-path
```

```bash
curl -sS http://127.0.0.1:8090/api/operator/path-comparison-current | head -c 4000
```

Confirm:

- HTTP 200 for route and API.
- payload includes `snapshot_date`, `warning`, `row_count`, `rows`.
- `rows[*].comparison_class` values are limited to:
  - `both`
  - `critical_only`
  - `computed_only`
- UI labels computed path as computed/non-authoritative and does not claim frontend logic ownership.

## Alternate Terminal Mismatch Investigation

Use diagnostic view `v_operator_path_comp_alt_terminal_mismatch_diag_current` to triage
`alternate_terminal_chain_mismatch` rows without changing classification logic.

### 1) Pull all rows by operator action signal

```sql
-- dependency normalization candidates
SELECT *
FROM v_operator_path_comp_alt_terminal_mismatch_diag_current
WHERE operator_action_signal = 'dependency_normalization_issue_candidate'
ORDER BY critical_path_sequence NULLS LAST, task_id;
```

```sql
-- terminal selection policy candidates
SELECT *
FROM v_operator_path_comp_alt_terminal_mismatch_diag_current
WHERE operator_action_signal = 'terminal_selection_policy_issue_candidate'
ORDER BY critical_path_sequence NULLS LAST, task_id;
```

```sql
-- likely true alternate finish-chain structure
SELECT *
FROM v_operator_path_comp_alt_terminal_mismatch_diag_current
WHERE operator_action_signal = 'true_alternate_finish_chain_structure_candidate'
ORDER BY reachable_alternate_terminal_count DESC, critical_path_sequence NULLS LAST, task_id;
```

### 2) Find top alternate terminal IDs by frequency

```sql
WITH expanded AS (
    SELECT
        d.snapshot_date,
        TRIM(term_id) AS alternate_terminal_task_id
    FROM v_operator_path_comp_alt_terminal_mismatch_diag_current d
    CROSS JOIN LATERAL regexp_split_to_table(
        COALESCE(d.alternate_terminal_task_ids, ''),
        ','
    ) AS term_id
    WHERE TRIM(term_id) <> ''
)
SELECT
    snapshot_date,
    alternate_terminal_task_id,
    COUNT(*)::integer AS occurrence_count
FROM expanded
GROUP BY snapshot_date, alternate_terminal_task_id
ORDER BY occurrence_count DESC, alternate_terminal_task_id ASC
LIMIT 25;
```

### 3) Prioritize highest alternate reachability rows

```sql
SELECT
    snapshot_date,
    task_id,
    task_name,
    selected_terminal_task_id,
    reachable_to_selected_terminal,
    component_connected_to_selected_terminal,
    reaches_finish_target,
    reachable_alternate_terminal_count,
    alternate_terminal_task_ids,
    dependency_qa_issue_present,
    operator_action_signal
FROM v_operator_path_comp_alt_terminal_mismatch_diag_current
ORDER BY reachable_alternate_terminal_count DESC, critical_path_sequence NULLS LAST, task_id
LIMIT 50;
```

### Interpretation guidance

- Treat as **normalization cleanup** when `operator_action_signal = 'dependency_normalization_issue_candidate'`
  or dependency QA counters (`parse_issue_count`, `missing_reference_count`, `ambiguous_reference_count`,
  `self_loop_count`, `duplicate_token_count`) are non-zero.
- Treat as **true alternate finish-chain investigation** when
  `operator_action_signal = 'true_alternate_finish_chain_structure_candidate'`,
  `dependency_qa_issue_present = false`, and `reachable_alternate_terminal_count` is consistently high.
- **Escalate terminal selection policy** when any rows appear with
  `operator_action_signal = 'terminal_selection_policy_issue_candidate'`, especially if selected terminal is
  not a graph sink (`selected_terminal_outbound_edge_count > 0`).
