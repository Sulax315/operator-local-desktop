-- Remove validation rows inserted by echarts_slip_validation_fixture_apply.sql
-- (and any optional tie-break rows sharing the same load_label).
DELETE FROM schedule_tasks
WHERE load_label = 'echarts_validation_fixture';
