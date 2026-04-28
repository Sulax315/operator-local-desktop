-- Assertion-style validation for computed_path_v1 regression fixtures.
-- Read-only checks against computed outputs and dependency QA artifacts.
-- Raises an exception on any mismatch.

DROP TABLE IF EXISTS tmp_regression_failures;
CREATE TEMP TABLE tmp_regression_failures (
    failure text NOT NULL
);

WITH expected_runs AS (
    SELECT *
    FROM (
        VALUES
            ('A_linear', DATE '2099-01-11', 'PASS', 4, 1, 4, 'LIN_4'),
            ('B_tie_break', DATE '2099-01-12', 'PASS', 2, 1, 2, 'TIE_JOIN'),
            ('C_terminal_finish_dominance', DATE '2099-01-13', 'PASS', 2, 1, 2, 'DOM_C'),
            ('D_cycle_fail_closed', DATE '2099-01-14', 'FAIL_CYCLE_DETECTED', 0, NULL::integer, NULL::integer, NULL::text),
            ('E_quarantine_exclusion', DATE '2099-01-15', 'PASS', 3, 1, 3, 'Q3')
    ) AS t(case_name, snapshot_date, expected_status, expected_row_count, expected_min_seq, expected_max_seq, expected_terminal_task_id)
)
INSERT INTO tmp_regression_failures (failure)
SELECT format(
    '%s: expected status=%s row_count=%s min_seq=%s max_seq=%s terminal=%s but got status=%s row_count=%s min_seq=%s max_seq=%s terminal=%s',
    e.case_name,
    e.expected_status,
    e.expected_row_count,
    COALESCE(e.expected_min_seq::text, 'NULL'),
    COALESCE(e.expected_max_seq::text, 'NULL'),
    COALESCE(e.expected_terminal_task_id, 'NULL'),
    COALESCE(r.graph_quality_status, 'NULL'),
    COALESCE(r.row_count::text, 'NULL'),
    COALESCE(r.min_path_sequence::text, 'NULL'),
    COALESCE(r.max_path_sequence::text, 'NULL'),
    COALESCE(r.terminal_task_id, 'NULL')
)
FROM expected_runs e
LEFT JOIN schedule_driver_path_computed_run r
    ON r.snapshot_date = e.snapshot_date
   AND r.algorithm_version = 'computed_path_v1'
WHERE r.snapshot_date IS NULL
   OR r.graph_quality_status <> e.expected_status
   OR r.row_count <> e.expected_row_count
   OR COALESCE(r.min_path_sequence, -999999) <> COALESCE(e.expected_min_seq, -999999)
   OR COALESCE(r.max_path_sequence, -999999) <> COALESCE(e.expected_max_seq, -999999)
   OR COALESCE(r.terminal_task_id, 'NULL') <> COALESCE(e.expected_terminal_task_id, 'NULL');

INSERT INTO tmp_regression_failures (failure)
SELECT format(
    '%s: PASS run has non-contiguous path_sequence (count=%s min=%s max=%s)',
    r.snapshot_date::text,
    agg.cnt::text,
    COALESCE(agg.min_seq::text, 'NULL'),
    COALESCE(agg.max_seq::text, 'NULL')
)
FROM schedule_driver_path_computed_run r
LEFT JOIN LATERAL (
    SELECT
        COUNT(*)::integer AS cnt,
        MIN(path_sequence)::integer AS min_seq,
        MAX(path_sequence)::integer AS max_seq
    FROM schedule_driver_path_computed c
    WHERE c.snapshot_date = r.snapshot_date
      AND c.algorithm_version = r.algorithm_version
) agg ON TRUE
WHERE r.algorithm_version = 'computed_path_v1'
  AND r.snapshot_date IN (
      DATE '2099-01-11',
      DATE '2099-01-12',
      DATE '2099-01-13',
      DATE '2099-01-15'
  )
  AND r.graph_quality_status = 'PASS'
  AND NOT (agg.cnt = agg.max_seq AND agg.min_seq = 1);

WITH expected_parents AS (
    SELECT *
    FROM (
        VALUES
            (DATE '2099-01-11', 'LIN_4', 'LIN_3'),
            (DATE '2099-01-12', 'TIE_JOIN', 'TIE_A'),
            (DATE '2099-01-13', 'DOM_C', 'DOM_A'),
            (DATE '2099-01-15', 'Q2', 'Q1'),
            (DATE '2099-01-15', 'Q3', 'Q2')
    ) AS t(snapshot_date, task_id, expected_parent_task_id)
)
INSERT INTO tmp_regression_failures (failure)
SELECT format(
    '%s/%s: expected selected_parent_task_id=%s but got %s',
    e.snapshot_date::text,
    e.task_id,
    e.expected_parent_task_id,
    COALESCE(c.selected_parent_task_id, 'NULL')
)
FROM expected_parents e
LEFT JOIN schedule_driver_path_computed c
    ON c.snapshot_date = e.snapshot_date
   AND c.algorithm_version = 'computed_path_v1'
   AND c.task_id = e.task_id
WHERE c.task_id IS NULL
   OR COALESCE(c.selected_parent_task_id, 'NULL') <> e.expected_parent_task_id;

INSERT INTO tmp_regression_failures (failure)
SELECT format('Cycle case produced computed rows (%s), expected 0', COUNT(*)::text)
FROM schedule_driver_path_computed
WHERE snapshot_date = DATE '2099-01-14'
  AND algorithm_version = 'computed_path_v1'
HAVING COUNT(*) <> 0;

INSERT INTO tmp_regression_failures (failure)
SELECT format('Quarantine case leaked excluded tasks into computed path: %s', string_agg(task_id, ', ' ORDER BY task_id))
FROM schedule_driver_path_computed
WHERE snapshot_date = DATE '2099-01-15'
  AND algorithm_version = 'computed_path_v1'
  AND task_id IN ('Q_SELF', 'Q_MISS', 'Q_AMB_1', 'Q_AMB_2', 'Q_AMB_SINK')
HAVING COUNT(*) > 0;

INSERT INTO tmp_regression_failures (failure)
SELECT format(
    'Quarantine raw-token counts mismatch: expected missing=1 ambiguous=1 self_loop=1; got missing=%s ambiguous=%s self_loop=%s',
    COUNT(*) FILTER (WHERE resolution_basis = 'missing')::text,
    COUNT(*) FILTER (WHERE resolution_basis = 'ambiguous')::text,
    COUNT(*) FILTER (WHERE is_self_loop)::text
)
FROM schedule_task_dependency_raw
WHERE snapshot_date = DATE '2099-01-15'
HAVING NOT (
    COUNT(*) FILTER (WHERE resolution_basis = 'missing') = 1
    AND COUNT(*) FILTER (WHERE resolution_basis = 'ambiguous') = 1
    AND COUNT(*) FILTER (WHERE is_self_loop) = 1
);

SELECT
    r.snapshot_date,
    r.graph_quality_status,
    r.row_count,
    r.min_path_sequence,
    r.max_path_sequence,
    r.terminal_task_id
FROM schedule_driver_path_computed_run r
WHERE r.algorithm_version = 'computed_path_v1'
  AND r.snapshot_date IN (
      DATE '2099-01-11',
      DATE '2099-01-12',
      DATE '2099-01-13',
      DATE '2099-01-14',
      DATE '2099-01-15'
  )
ORDER BY r.snapshot_date;

DO $$
DECLARE
    v_failure_count integer;
    v_failure_text text;
BEGIN
    SELECT COUNT(*) INTO v_failure_count
    FROM tmp_regression_failures;

    IF v_failure_count > 0 THEN
        SELECT string_agg(failure, E'\n')
        INTO v_failure_text
        FROM tmp_regression_failures;

        RAISE EXCEPTION 'computed_path_v1 regression validation failed (%): %',
            v_failure_count,
            v_failure_text;
    END IF;
END $$;

SELECT 'computed_driver_path_regression_validation: PASS' AS result;
