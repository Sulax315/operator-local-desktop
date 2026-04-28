# ECharts — Computed Driver Path (v1)

## What this chart means

This operator surface visualizes **computed path** rows from SQL view `v_operator_driver_path_computed_current`.

- Source semantics remain in Postgres SQL only.
- Rows are already ordered by SQL `path_sequence`.
- The API and browser perform serialization and chart projection only.

## What this chart does not mean

- It is **not** engine-authoritative Asta driving path truth.
- It does **not** replace import-authoritative path contracts in `docs/driver_path_data_contract.md`.
- It does **not** perform pathfinding in Python or JavaScript.

Use this view for operator analysis of the computed proxy, not for authoritative driving-path claims.

## Endpoint and route

- API: `GET /api/operator/computed-driver-path-current`
- Page: `GET /computed-path`

Response fields include:

- `snapshot_date`
- `algorithm_version`
- `graph_quality_status`
- `graph_quality_notes`
- `rows[]` with:
  - `path_sequence`
  - `task_id`
  - `task_name`
  - `start_date`
  - `finish_date`
  - `total_float_days`
  - `critical`
  - `percent_complete`
  - `selected_parent_task_id`

## Prerequisites

1. `schedule_tasks` loaded for snapshots.
2. Dependency graph refreshed:
   - `sql/06_refresh_dependency_graph.sql`
3. Computed path refreshed:
   - `sql/07_refresh_computed_driver_path.sql`
4. Operator ECharts service running.

## Refresh and verify (exact commands)

From repo root:

```bash
DB_CONTAINER=9e60004df82e_bratek-phase1-postgres
DB_USER=bratek_ops
DB_NAME=postgres

docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < sql/06_refresh_dependency_graph.sql
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < sql/07_refresh_computed_driver_path.sql

curl -sS http://127.0.0.1:8090/api/operator/computed-driver-path-current | head -c 3000
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/computed-path
```

Optional SQL verification:

```bash
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c \
  "SELECT * FROM v_schedule_driver_path_computed_inventory ORDER BY snapshot_date DESC, computed_at DESC LIMIT 5;"

docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c \
  "SELECT * FROM v_operator_driver_path_computed_current ORDER BY path_sequence;"
```

## Navigation

The operator ECharts nav now includes:

- Recently Slipped
- Critical Tasks (Current Snapshot)
- Computed Path (v1)

## Future authoritative path note

If an engine-authoritative imported path becomes available in future, it remains a **separate** concept and dataset from this computed-path surface.
