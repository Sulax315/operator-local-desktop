-- Deterministic fixtures for computed_path_v1 regression locking.
-- Safe to re-run: fixture snapshot rows are replaced in-place.
-- Cases:
--   A) Simple linear chain
--   B) Deterministic parent tie-break
--   C) Terminal-finish dominance over cleaner/longer branch
--   D) Cycle fail-closed
--   E) Quarantine (missing/ambiguous/self-loop) exclusion

WITH fixture_snapshots AS (
    SELECT unnest(ARRAY[
        DATE '2099-01-11', -- A: linear
        DATE '2099-01-12', -- B: tie-break
        DATE '2099-01-13', -- C: terminal-finish dominance
        DATE '2099-01-14', -- D: cycle
        DATE '2099-01-15'  -- E: quarantine
    ]) AS snapshot_date
)
DELETE FROM schedule_driver_path_computed
WHERE algorithm_version = 'computed_path_v1'
  AND snapshot_date IN (SELECT snapshot_date FROM fixture_snapshots);

WITH fixture_snapshots AS (
    SELECT unnest(ARRAY[
        DATE '2099-01-11',
        DATE '2099-01-12',
        DATE '2099-01-13',
        DATE '2099-01-14',
        DATE '2099-01-15'
    ]) AS snapshot_date
)
DELETE FROM schedule_driver_path_computed_run
WHERE algorithm_version = 'computed_path_v1'
  AND snapshot_date IN (SELECT snapshot_date FROM fixture_snapshots);

WITH fixture_snapshots AS (
    SELECT unnest(ARRAY[
        DATE '2099-01-11',
        DATE '2099-01-12',
        DATE '2099-01-13',
        DATE '2099-01-14',
        DATE '2099-01-15'
    ]) AS snapshot_date
)
DELETE FROM schedule_task_dependency_edge
WHERE snapshot_date IN (SELECT snapshot_date FROM fixture_snapshots);

WITH fixture_snapshots AS (
    SELECT unnest(ARRAY[
        DATE '2099-01-11',
        DATE '2099-01-12',
        DATE '2099-01-13',
        DATE '2099-01-14',
        DATE '2099-01-15'
    ]) AS snapshot_date
)
DELETE FROM schedule_task_dependency_raw
WHERE snapshot_date IN (SELECT snapshot_date FROM fixture_snapshots);

WITH fixture_snapshots AS (
    SELECT unnest(ARRAY[
        DATE '2099-01-11',
        DATE '2099-01-12',
        DATE '2099-01-13',
        DATE '2099-01-14',
        DATE '2099-01-15'
    ]) AS snapshot_date
)
DELETE FROM schedule_tasks
WHERE snapshot_date IN (SELECT snapshot_date FROM fixture_snapshots);

INSERT INTO schedule_tasks (
    snapshot_date,
    load_label,
    task_id,
    task_name,
    unique_task_id,
    start_date,
    finish_date,
    total_float_days,
    predecessors,
    percent_complete
)
VALUES
    -- A) Simple linear chain (expected path: LIN_1 -> LIN_2 -> LIN_3 -> LIN_4)
    (DATE '2099-01-11', 'computed_path_regression_fixture_v1', 'LIN_1', 'Linear root', NULL, DATE '2099-01-01', DATE '2099-01-02', 0, NULL, 0),
    (DATE '2099-01-11', 'computed_path_regression_fixture_v1', 'LIN_2', 'Linear step 2', NULL, DATE '2099-01-03', DATE '2099-01-04', 0, 'LIN_1', 0),
    (DATE '2099-01-11', 'computed_path_regression_fixture_v1', 'LIN_3', 'Linear step 3', NULL, DATE '2099-01-05', DATE '2099-01-06', 1, 'LIN_2', 0),
    (DATE '2099-01-11', 'computed_path_regression_fixture_v1', 'LIN_4', 'Linear terminal', NULL, DATE '2099-01-07', DATE '2099-01-08', 1, 'LIN_3', 0),

    -- B) Parent tie-break: TIE_JOIN has two equal-scored parents; lexical parent task_id wins.
    -- Expected selected parent for TIE_JOIN: TIE_A (over TIE_B).
    (DATE '2099-01-12', 'computed_path_regression_fixture_v1', 'TIE_A', 'Tie parent A', NULL, DATE '2099-01-01', DATE '2099-01-03', 1, NULL, 0),
    (DATE '2099-01-12', 'computed_path_regression_fixture_v1', 'TIE_B', 'Tie parent B', NULL, DATE '2099-01-01', DATE '2099-01-03', 1, NULL, 0),
    (DATE '2099-01-12', 'computed_path_regression_fixture_v1', 'TIE_JOIN', 'Tie join terminal', NULL, DATE '2099-01-04', DATE '2099-01-10', 0, 'TIE_A,TIE_B', 0),

    -- C) Terminal-finish dominance:
    -- Branch 1 (cleaner/longer): DOM_A -> DOM_B -> DOM_B2 (terminal finish 2099-01-24, lower penalty, longer)
    -- Branch 2 (shorter/dirtier): DOM_A -> DOM_C (terminal finish 2099-01-26, higher penalty, shorter)
    -- Expected terminal: DOM_C because terminal finish_date is primary score.
    (DATE '2099-01-13', 'computed_path_regression_fixture_v1', 'DOM_A', 'Dominance root', NULL, DATE '2099-01-01', DATE '2099-01-05', 0, NULL, 0),
    (DATE '2099-01-13', 'computed_path_regression_fixture_v1', 'DOM_B', 'Cleaner branch mid', NULL, DATE '2099-01-06', DATE '2099-01-12', 0, 'DOM_A', 0),
    (DATE '2099-01-13', 'computed_path_regression_fixture_v1', 'DOM_B2', 'Cleaner branch terminal', NULL, DATE '2099-01-13', DATE '2099-01-24', 0, 'DOM_B', 0),
    (DATE '2099-01-13', 'computed_path_regression_fixture_v1', 'DOM_C', 'Later terminal higher penalty', NULL, DATE '2099-01-06', DATE '2099-01-26', 30, 'DOM_A', 0),

    -- D) Cycle fail-closed: CYC_A -> CYC_B -> CYC_C -> CYC_A
    (DATE '2099-01-14', 'computed_path_regression_fixture_v1', 'CYC_A', 'Cycle A', NULL, DATE '2099-01-01', DATE '2099-01-03', 0, 'CYC_C', 0),
    (DATE '2099-01-14', 'computed_path_regression_fixture_v1', 'CYC_B', 'Cycle B', NULL, DATE '2099-01-04', DATE '2099-01-05', 0, 'CYC_A', 0),
    (DATE '2099-01-14', 'computed_path_regression_fixture_v1', 'CYC_C', 'Cycle C', NULL, DATE '2099-01-06', DATE '2099-01-07', 0, 'CYC_B', 0),

    -- E) Quarantine case: unresolved / ambiguous / self-loop tokens are excluded upstream.
    -- Valid chain expected in traversal: Q1 -> Q2 -> Q3
    (DATE '2099-01-15', 'computed_path_regression_fixture_v1', 'Q1', 'Quarantine valid root', NULL, DATE '2099-01-01', DATE '2099-01-02', 0, NULL, 0),
    (DATE '2099-01-15', 'computed_path_regression_fixture_v1', 'Q2', 'Quarantine valid middle', NULL, DATE '2099-01-03', DATE '2099-01-04', 0, 'Q1', 0),
    (DATE '2099-01-15', 'computed_path_regression_fixture_v1', 'Q3', 'Quarantine valid terminal', NULL, DATE '2099-01-05', DATE '2099-01-06', 0, 'Q2', 0),

    -- Self-loop token -> should remain in raw QA and be excluded from promoted edges.
    (DATE '2099-01-15', 'computed_path_regression_fixture_v1', 'Q_SELF', 'Self loop quarantine token', NULL, DATE '2099-01-03', DATE '2099-01-04', 5, 'Q_SELF', 0),
    -- Missing token -> unresolved reference.
    (DATE '2099-01-15', 'computed_path_regression_fixture_v1', 'Q_MISS', 'Missing predecessor quarantine token', NULL, DATE '2099-01-03', DATE '2099-01-04', 5, 'NO_SUCH_TASK', 0),
    -- Ambiguous unique_task_id token (two matches).
    (DATE '2099-01-15', 'computed_path_regression_fixture_v1', 'Q_AMB_1', 'Ambiguous source 1', 'DUPKEY', DATE '2099-01-01', DATE '2099-01-02', 0, NULL, 0),
    (DATE '2099-01-15', 'computed_path_regression_fixture_v1', 'Q_AMB_2', 'Ambiguous source 2', 'DUPKEY', DATE '2099-01-01', DATE '2099-01-02', 0, NULL, 0),
    (DATE '2099-01-15', 'computed_path_regression_fixture_v1', 'Q_AMB_SINK', 'Ambiguous sink token', NULL, DATE '2099-01-03', DATE '2099-01-05', 0, 'DUPKEY', 0);
