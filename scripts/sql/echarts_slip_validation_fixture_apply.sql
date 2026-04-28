-- Reversible validation data for Phase 4 ECharts (recently slipped tasks).
-- Does NOT alter views or signal logic — inserts schedule_tasks rows only.
--
-- Inserts three tasks sharing the same positive slip (20 days) against
-- v_schedule_snapshot_pair_latest, with task_ids ordered for tie-break checks:
--   echarts_fixture_slip, fixture_tie_a, fixture_tie_z
--
-- Revert: scripts/sql/echarts_slip_validation_fixture_revert.sql

WITH pair AS (
    SELECT prior_snapshot_date, current_snapshot_date
    FROM v_schedule_snapshot_pair_latest
    LIMIT 1
),
ins AS (
    SELECT * FROM (VALUES
        ('echarts_fixture_slip', 'ECharts non-empty validation fixture (reversible via load_label)'),
        ('fixture_tie_a', 'Tie-break validation row A'),
        ('fixture_tie_z', 'Tie-break validation row Z')
    ) AS t(task_id, task_name)
)
INSERT INTO schedule_tasks (
    snapshot_date,
    load_label,
    task_id,
    task_name,
    start_date,
    finish_date,
    percent_complete
)
SELECT
    p.prior_snapshot_date,
    'echarts_validation_fixture',
    i.task_id,
    i.task_name,
    p.prior_snapshot_date,
    p.prior_snapshot_date + 25,
    0
FROM pair p
CROSS JOIN ins i
UNION ALL
SELECT
    p.current_snapshot_date,
    'echarts_validation_fixture',
    i.task_id,
    i.task_name,
    p.current_snapshot_date,
    p.prior_snapshot_date + 45,
    0
FROM pair p
CROSS JOIN ins i
ON CONFLICT (snapshot_date, task_id) DO NOTHING;
