# Schedule Question Pack (First 25 Asta Questions)

This pack provides a first-pass, production-ready SQL view layer for schedule intelligence using `schedule_tasks` as the normalized source table.

## Files

- `sql/08_schedule_question_views.sql` - helper and question views
- `sql/09_schedule_question_validation.sql` - compile/run validation selects

## Source Dependencies

Required table:

- `schedule_tasks`

Required columns used by this pack:

- `snapshot_date`
- `task_id`
- `task_name`
- `unique_task_id`
- `start_date`
- `finish_date`
- `early_start`
- `early_finish`
- `late_start`
- `late_finish`
- `total_float_days`
- `free_float_days`
- `critical`
- `predecessors`
- `successors`
- `critical_path_drag_days`
- `area_zone`
- `csi`
- `percent_complete`
- `original_finish`

## Schema Notes vs Assumptions

- Actual `schedule_tasks.critical` type is `text` (not boolean). This pack normalizes critical flags from text values (`TRUE/YES/Y/1` etc.).
- Actual `schedule_tasks.duration` and `schedule_tasks.duration_remaining` are `text` in this repo; this pack avoids numeric logic on those fields.
- Existing snapshot helper `v_schedule_snapshot_pair_latest` is already present in `sql/04_signals.sql`. This pack adds parallel helper views scoped specifically for this question set.

## Helper Views

- `v_schedule_latest_snapshot` - latest available snapshot date
- `v_schedule_prior_snapshot` - prior snapshot date (if available)
- `v_schedule_current_tasks` - `schedule_tasks` rows for latest snapshot, with normalized helper fields
- `v_schedule_prior_tasks` - `schedule_tasks` rows for prior snapshot, with normalized helper fields
- `v_schedule_current_vs_prior_tasks` - aligned current/prior task rows by `unique_task_id` fallback key (`task_id`) with deterministic rank matching

## Semantic Rules (Locked)

- **Critical normalization rule**
  - `normalized_critical_flag = true` when `UPPER(COALESCE(critical, '')) IN ('TRUE', 'YES', 'Y', '1')`
  - `normalized_critical_flag = false` when `UPPER(COALESCE(critical, '')) IN ('FALSE', 'NO', 'N', '0')`
  - Otherwise `normalized_critical_flag = NULL`
- **Low-float rule**
  - Low-float means `total_float_days BETWEEN 0 AND 5` (inclusive), and incomplete only
- **Incomplete rule**
  - Incomplete means `COALESCE(percent_complete, 0) < 100`
- **Next-14-days anchor rule**
  - All "next 14 days" windows are anchored to the latest `snapshot_date`, not wall-clock date
  - Anchor values are exposed in `v_schedule_current_tasks` as `snapshot_anchor_date` and `next_14_days_end_date`
- **Current/prior matching rule**
  - Match key is `COALESCE(NULLIF(BTRIM(unique_task_id), ''), task_id)`
  - Current/prior alignment uses full outer join on `task_match_key + deterministic ROW_NUMBER rank by task_id`

## View-to-Question Map

1. Current projected completion date  
   - `v_schedule_current_project_finish`  
   - Scope: latest snapshot only

2. Latest-finishing task(s)  
   - `v_schedule_latest_finishing_tasks`  
   - Scope: latest snapshot only

3. Count of critical incomplete tasks  
   - `v_schedule_critical_incomplete_task_count`  
   - Scope: latest snapshot only

4. List of critical incomplete tasks  
   - `v_schedule_critical_incomplete_tasks`  
   - Scope: latest snapshot only

5. Count of low-float tasks  
   - `v_schedule_low_float_task_count`  
   - Scope: latest snapshot only

6. List of low-float tasks  
   - `v_schedule_low_float_tasks`  
   - Scope: latest snapshot only

7. Negative-float tasks  
   - `v_schedule_negative_float_tasks`  
   - Scope: latest snapshot only

8. Critical tasks starting in next 14 days  
   - `v_schedule_critical_starts_next_14_days`  
   - Scope: latest snapshot only

9. Critical tasks finishing in next 14 days  
   - `v_schedule_critical_finishes_next_14_days`  
   - Scope: latest snapshot only

10. All incomplete tasks starting in next 14 days  
    - `v_schedule_incomplete_starts_next_14_days`  
    - Scope: latest snapshot only

11. All incomplete tasks finishing in next 14 days  
    - `v_schedule_incomplete_finishes_next_14_days`  
    - Scope: latest snapshot only

12. Tasks slipped beyond original finish  
    - `v_schedule_tasks_slipped_beyond_original_finish`  
    - Scope: latest snapshot only

13. Top 25 biggest finish-date slips  
    - `v_schedule_top_25_biggest_finish_slips`  
    - Scope: latest snapshot only

14. Schedule completion variance vs original completion  
    - `v_schedule_completion_variance_vs_original`  
    - Scope: latest snapshot only

15. Tasks with no predecessors  
    - `v_schedule_tasks_with_no_predecessors`  
    - Scope: latest snapshot only

16. Tasks with no successors  
    - `v_schedule_tasks_with_no_successors`  
    - Scope: latest snapshot only

17. Incomplete tasks with no predecessors  
    - `v_schedule_incomplete_tasks_with_no_predecessors`  
    - Scope: latest snapshot only

18. Incomplete tasks with no successors  
    - `v_schedule_incomplete_tasks_with_no_successors`  
    - Scope: latest snapshot only

19. Tasks with highest critical path drag  
    - `v_schedule_tasks_highest_critical_path_drag`  
    - Scope: latest snapshot only

20. Critical tasks with highest drag  
    - `v_schedule_critical_tasks_highest_drag`  
    - Scope: latest snapshot only

21. Areas with the most critical work  
    - `v_schedule_areas_most_critical_work`  
    - Scope: latest snapshot only

22. CSI divisions with the most critical work  
    - `v_schedule_csi_divisions_most_critical_work`  
    - Scope: latest snapshot only

23. Areas with the most low-float work  
    - `v_schedule_areas_most_low_float_work`  
    - Scope: latest snapshot only

24. Tasks changed dates since prior snapshot  
    - `v_schedule_tasks_changed_dates_since_prior_snapshot`  
    - Scope: current vs prior snapshot

25. Tasks changed critical status since prior snapshot  
    - `v_schedule_tasks_changed_critical_status_since_prior_snapshot`  
    - Scope: current vs prior snapshot

## Assumptions and Limitations

- Low-float threshold is set to `0..5` days (`total_float_days`) and incomplete-only filtering.
- "Next 14 days" windows are anchored to latest `snapshot_date` (not server `CURRENT_DATE`) for deterministic snapshot behavior.
- Current/prior comparisons require at least two snapshots; if prior snapshot is missing, comparison views return zero rows.
- Alignment key uses `unique_task_id` where available, otherwise falls back to `task_id`.

## Audit Views

- `v_schedule_snapshot_key_health`
  - Row counts by snapshot
  - Duplicate `task_id` row counts by snapshot
  - Duplicate `unique_task_id` row counts by snapshot
- `v_schedule_duplicate_task_key_check`
  - Detailed duplicate key groups for `task_id` and `unique_task_id`
- `v_schedule_current_prior_match_audit`
  - Matched current/prior rows
  - Unmatched current rows
  - Unmatched prior rows
