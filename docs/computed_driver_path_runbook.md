# Computed driver path runbook (non-authoritative)

This runbook describes the SQL-only computed driver-path proxy for Bratek Operator Stack.

## What this is

- A deterministic path proxy computed from `schedule_task_dependency_edge`.
- Built inside Postgres only (`sql/07_refresh_computed_driver_path.sql`).
- Named explicitly as **computed**:
  - `schedule_driver_path_computed`
  - `v_operator_driver_path_computed_current`

## What this is not

- Not Asta/engine-authoritative driving path truth.
- Not a replacement for the export-authoritative contract in `docs/driver_path_data_contract.md`.
- Not a UI/ECharts path computation layer.

## Algorithm version

- `computed_path_v1`
- Behavior is regression-locked by deterministic SQL fixtures in:
  - `scripts/sql/computed_driver_path_regression_fixture.sql`
  - `scripts/sql/computed_driver_path_regression_validate.sql`

## Preconditions

1. `schedule_tasks` is loaded for target snapshots.
2. Dependency normalization has been refreshed:
   - `sql/06_refresh_dependency_graph.sql`
3. Promoted edges exist in `schedule_task_dependency_edge`.

## Candidate policy

- Incomplete tasks only: `COALESCE(percent_complete, 0) < 100`
- Task must be connected via promoted edges (incoming or outgoing edge).
- Quarantined references from Phase 1b are excluded by design:
  - unresolved
  - ambiguous
  - self-loop
  - parse error rows

## Scoring policy (deterministic)

Path selection order:

1. Maximize terminal `finish_date`
2. Minimize cumulative float penalty
   - node penalty = `GREATEST(COALESCE(total_float_days, 0), 0)`
3. Maximize path length
4. Tie-break by lexical terminal `task_id`

Parent selection at each node:

1. Minimize candidate cumulative penalty
2. Maximize candidate path length
3. Tie-break by lexical predecessor `task_id`

## Cycle policy

- Fail-closed per snapshot.
- Cycle detection uses deterministic Kahn-style peeling on candidate graph.
- If cycle remains, run status is `FAIL_CYCLE_DETECTED` and no computed rows are written for that snapshot.

## How to run

From repo root:

```bash
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < sql/07_refresh_computed_driver_path.sql
```

Example defaults from current stack:

```bash
DB_CONTAINER=bratek-phase1-postgres
DB_USER=bratek_ops
DB_NAME=postgres
```

## Regression fixture purpose

- Lock `computed_path_v1` behavior before downstream expansion/UI consumption.
- Provide deterministic coverage for:
  - simple linear chain
  - deterministic parent tie-break
  - terminal-finish dominance (primary score precedence)
  - cycle fail-closed behavior
  - quarantine exclusion (missing/ambiguous/self-loop)

## Regression commands (exact sequence)

From repo root:

```bash
DB_CONTAINER=9e60004df82e_bratek-phase1-postgres
DB_USER=bratek_ops
DB_NAME=postgres

docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < scripts/sql/computed_driver_path_regression_fixture.sql
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < sql/06_refresh_dependency_graph.sql
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < sql/07_refresh_computed_driver_path.sql
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < scripts/sql/computed_driver_path_regression_validate.sql
```

Expected validation output includes:

- Five run rows for fixture snapshots:
  - `2099-01-11` => `PASS` (linear)
  - `2099-01-12` => `PASS` (tie-break)
  - `2099-01-13` => `PASS` (terminal-finish dominance)
  - `2099-01-14` => `FAIL_CYCLE_DETECTED` with `row_count = 0`
  - `2099-01-15` => `PASS` (quarantine exclusion)
- Final line: `computed_driver_path_regression_validation: PASS`

If any expectation drifts, `computed_driver_path_regression_validate.sql` raises an exception and exits non-zero.

## Validation and sanity checks

Inventory:

```sql
SELECT *
FROM v_schedule_driver_path_computed_inventory
ORDER BY snapshot_date DESC, algorithm_version;
```

Sequence validity for PASS snapshots:

```sql
SELECT
  snapshot_date,
  algorithm_version,
  COUNT(*) AS row_count,
  MIN(path_sequence) AS min_seq,
  MAX(path_sequence) AS max_seq
FROM schedule_driver_path_computed
GROUP BY snapshot_date, algorithm_version
ORDER BY snapshot_date DESC, algorithm_version;
```

Contiguity check:

```sql
SELECT
  snapshot_date,
  algorithm_version,
  (COUNT(*) = MAX(path_sequence) AND MIN(path_sequence) = 1) AS contiguous_sequence
FROM schedule_driver_path_computed
GROUP BY snapshot_date, algorithm_version
ORDER BY snapshot_date DESC, algorithm_version;
```

Current-snapshot projection:

```sql
SELECT *
FROM v_operator_driver_path_computed_current
ORDER BY path_sequence;
```

## Notes on exclusions

- Edges are computed from promoted dependency edges only.
- Any unresolved/ambiguous/self-loop dependency tokens remain visible in Phase 1b QA and are excluded from traversal.
- If a snapshot fails cycle checks, no fallback “best effort” path is emitted.
