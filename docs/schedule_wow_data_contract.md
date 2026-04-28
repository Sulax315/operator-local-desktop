# Week-over-week schedule drift data contract

## Purpose

This contract defines the minimum data and matching rules required to compute repeatable week-over-week (WoW) schedule drift analytics from ASTA exports for a single job.

The canonical source remains `schedule_tasks` in Postgres. WoW views are derived from snapshot pairs in SQL; no schedule business logic is implemented in Metabase.

## Source file contract

Each ASTA export CSV must include these headers:

- `Task ID`
- `Task name`
- `Unique task ID`
- `Start`
- `Finish`
- `Total float`
- `Free float`
- `Critical`
- `Predecessors`
- `Successors`
- `Phase Exec`
- `Control Account`
- `Area Zone`
- `Level`
- `CSI`
- `System`
- `Percent complete`
- `Original start`
- `Original finish`

Existing ingestion also consumes `Duration`, `Duration remaining`, `Early start`, `Early finish`, `Late start`, `Late finish`, and `Critical path drag`.

## Snapshot identity contract

- A snapshot is identified by `snapshot_date` supplied to the loader (`YYYY-MM-DD`).
- A row in `schedule_tasks` is unique by `(snapshot_date, task_id)` (`uq_schedule_tasks`).
- Source-level row matching across snapshots is performed with:
  - primary key: normalized `unique_task_id` when present
  - fallback key: `task_id` when `unique_task_id` is blank
  - duplicate disambiguation: `ROW_NUMBER()` by `task_match_key` ordered by `task_id`

This prevents false 1:N joins when duplicate keys appear in a snapshot.

## Normalization contract

- Date strings are parsed as `MM/DD/YYYY`.
- Float and progress fields are parsed by stripping non-numeric characters (for values like `0d`).
- `critical` is normalized to boolean using accepted truthy/falsy values:
  - true: `TRUE`, `YES`, `Y`, `1`
  - false: `FALSE`, `NO`, `N`, `0`

## WoW comparison contract

The latest pair comes from `v_schedule_snapshot_pair_latest`:

- `current_snapshot_date`: max snapshot date
- `prior_snapshot_date`: previous max snapshot date

Row-level deltas include:

- `start_delta_days`
- `finish_delta_days`
- `total_float_delta_days`
- `critical_transition`
- `status_change_class`

`status_change_class` values:

- `added`
- `removed`
- `slipped`
- `pulled_in`
- `start_shift_only`
- `unchanged`

## Visualization-facing view contract

The WoW analytics layer publishes these views:

- `v_schedule_wow_task_delta_latest_pair` (base task-level delta)
- `v_schedule_wow_kpi_strip`
- `v_schedule_wow_slip_distribution`
- `v_schedule_wow_heatmap_phase_control`
- `v_schedule_wow_critical_transition_matrix`
- `v_schedule_wow_top_risk_tasks`
- `v_schedule_wow_change_class_waterfall`
- `v_schedule_wow_timeline_drilldown`

These are intended to be query-stable contracts for BI tooling and API publishers.

## Validation expectations

- At least two distinct snapshot dates exist before WoW views are consumed.
- Snapshot pair dates are non-null in `v_schedule_snapshot_pair_latest`.
- KPI totals reconcile to counts from `v_schedule_wow_task_delta_latest_pair`.
- Rerunning load + view refresh is idempotent for the same snapshot date (no duplicate `schedule_tasks` inserts).
