# Metabase Dashboard Validation - Operator Productivity Control Loop v1

## Scope
Validate that Metabase dashboard `Operator Productivity Control Loop - v1` is implemented per spec and reconciles with validated SQL evidence.

Specification source:
- `docs/metabase_productivity_operator_dashboard_spec.md`

Evidence source used for reconciliation:
- `build_control/productivity_loop/phase1_validation_evidence.md`
- Intake cycle section: `WAVERLY` + `foundation_waterproofing_west`

## Dashboard Implementation Result
- Dashboard name: `Operator Productivity Control Loop - v1`
- Dashboard id: `4`
- Collection id: `4` (`jake bratek's Personal Collection`)
- Data source: Metabase database `Schedule DB` (id `2`)

## Cards Implemented
1. `Scope Productivity Leaderboard` (card id `64`, display `table`)
   - Source view: `v_scope_productivity`
   - Sort: `productivity_variance` descending
2. `Under-Baseline Scopes` (card id `65`, display `table`)
   - Source view: `v_scope_productivity`
   - Filter: `productivity_variance < 0`
   - Sort: `productivity_variance` ascending
3. `Baseline vs Actual Productivity (By Scope)` (card id `66`, display `bar`)
   - Source view: `v_scope_productivity`
   - Sort: `scope_code` ascending
4. `Baseline Context Table` (card id `67`, display `table`)
   - Source view: `v_scope_baseline`
   - Sort: `project_code`, then `scope_code`
5. `Actual Production Context Table` (card id `68`, display `table`)
   - Source view: `v_scope_actual`
   - Sort: `project_code`, then `scope_code`

## Dashboard Filters Configured
- Dashboard parameters:
  - `project_code` (category)
  - `scope_code` (category)
- Parameter mappings applied across all five cards using corresponding view field ids.

## Reconciliation Dataset
- `project_code = WAVERLY`
- `scope_code = foundation_waterproofing_west`

Expected evidence values (from `phase1_validation_evidence.md`):
- `baseline_quantity = 12600.000`
- `planned_install_days = 18.00`
- `baseline_productivity = 700.0000000000000000`
- `total_installed_quantity = 12150.000`
- `actual_work_days = 3`
- `actual_productivity = 4050.0000000000000000`
- `productivity_variance = 4.7857142857142857`

Observed Metabase values (via card query execution):
- `Scope Productivity Leaderboard`:
  - `baseline_productivity = 700.0`
  - `actual_productivity = 4050.0`
  - `productivity_variance = 4.785714285714286`
- `Baseline Context Table`:
  - `baseline_quantity = 12600.0`
  - `planned_install_days = 18.0`
  - `baseline_productivity = 700.0`
- `Actual Production Context Table`:
  - `total_installed_quantity = 12150.0`
  - `actual_work_days = 3`
  - `actual_productivity = 4050.0`

Rounding note:
- Metabase display precision is shorter than SQL text output, but numeric values reconcile.

## PASS/FAIL
- **Dashboard implementation vs spec:** PASS
- **SQL-view-only sourcing:** PASS
- **No custom logic/calculated fields:** PASS
- **Evidence reconciliation:** PASS

## Validation Artifact
- API execution result file: `runtime/metabase_operator_dashboard_build_result.json`

---

## Operator UAT Pass - v1 Sign-off

### Timestamp
- `2026-04-14T18:27:25Z` (UTC)

### Dashboard
- Name: `Operator Productivity Control Loop - v1`
- Dashboard id: `4`

### Scopes Reviewed (real)
1. `WAVERLY` + `foundation_waterproofing_west`
2. `WAVERLY` + `structural_frame_p1_cfmf`

### Filters Applied
- `project_code = WAVERLY`
- `scope_code = foundation_waterproofing_west` (pass 1)
- `scope_code = structural_frame_p1_cfmf` (pass 2)

### UAT Observations
- Card data remained internally consistent across:
  - `Scope Productivity Leaderboard`
  - `Under-Baseline Scopes`
  - `Baseline Context Table`
  - `Actual Production Context Table`
  - `Baseline vs Actual Productivity (By Scope)`
- Reconciled values for `foundation_waterproofing_west` matched evidence:
  - baseline: `12600`, planned days: `18`, baseline productivity: `700`
  - actual total: `12150`, work days: `3`, actual productivity: `4050`
  - variance: `4.7857142857142857` (display-rounded in Metabase)
- Reconciled values for `structural_frame_p1_cfmf` matched evidence:
  - baseline: `9000`, planned days: `15`, baseline productivity: `600`
  - actual total: `5950`, work days: `3`, actual productivity: `1983.3333333333333`
  - variance: `2.3055555555555556`
- `Under-Baseline Scopes` correctly returned no rows for these two scopes (both positive variance).

### Issues / Operator Confusion Points
- **Filter behavior note:** Dashboard-query API based UAT (`/api/dashboard/{id}/dashcard/{dashcard-id}/card/{card-id}/query`) did not reduce returned row sets when parameter payloads were provided; rows for other scopes still appeared.
- Impact:
  - Numeric reconciliation for target scopes is still valid.
  - API-level filter behavior requires follow-up verification directly in interactive dashboard UI for operator experience certainty.

### Final Verdict
- **PASS WITH NOTES**

### UAT Artifact
- `runtime/metabase_operator_uat_result.json`

---

## Final UI Filter Validation

### Timestamp
- `2026-04-15` (interactive Metabase UI validation)

### Dashboard
- Name: `Operator Productivity Control Loop - v1`
- Dashboard id: `4`

### Test Matrix
1. **Test A**
   - `project_code = WAVERLY`
   - `scope_code = foundation_waterproofing_west`
2. **Test B**
   - `project_code = WAVERLY`
   - `scope_code = structural_frame_p1_cfmf`
3. **Test C**
   - `project_code = WAVERLY`
   - no `scope_code`

### Observations
- In all three tests, the dashboard URL/state reflected filter values and the filter chips showed active selections (with clear buttons visible).
- However, card rowsets remained unchanged and still included unrelated rows (for example `PRJ-001` and non-selected scopes) across:
  - `Scope Productivity Leaderboard`
  - `Baseline Context Table`
  - `Actual Production Context Table`
- Expected selected-scope values (`foundation_waterproofing_west` and `structural_frame_p1_cfmf`) were still present and numerically consistent with prior evidence, but filtering did not constrain the full dataset.
- No UI-only pathway in this session produced card-level filtered rowsets for the selected values.

### PASS/FAIL (Final UI Filter Validation)
- **UI filter behavior across cards:** FAIL
- **Unexpected rows under active filters:** FAIL
- **Metric consistency for target scopes:** PASS (values still reconcile)

### Final Verdict (v1 Sign-off)
- **FAIL (UI filter behavior not enforcing scope/project constraints across cards)**

---

## Filter Mapping Remediation + Re-Validation

### Timestamp
- `2026-04-15` (interactive UI remediation session)

### Remediation Scope Executed
- Entered dashboard edit mode for `Operator Productivity Control Loop - v1`.
- Opened filter configuration UI for `project_code` and `scope_code`.
- Inspected filter configuration panels, including filter settings and linked-filter tabs.
- Attempted explicit per-card remapping flow (disconnect + reconnect path) for `project_code` using the UI "Column to filter on" selectors.

### Root Cause Assessment
- Dashboard filters are present in the UI, but card rowsets remain unconstrained under active filter values.
- Operationally, this indicates filter-to-card field mapping is not being enforced as expected across cards in current dashboard state.
- During remediation, per-card selector controls were intermittently available but not stably operable in this session; no trusted, persisted remap state could be confirmed.

### Re-Validation Tests
1. **Test A**
   - `project_code = WAVERLY`
   - `scope_code = foundation_waterproofing_west`
   - Result: FAIL (unrelated rows, including `PRJ-001`, still present)
2. **Test B**
   - `project_code = WAVERLY`
   - `scope_code = structural_frame_p1_cfmf`
   - Result: FAIL (rowsets still include non-target scopes/projects)
3. **Test C**
   - `project_code = WAVERLY`
   - no `scope_code`
   - Result: FAIL (non-`WAVERLY` rows still present)

### PASS/FAIL (Remediation Re-Validation)
- **Filter mapping remediation outcome:** FAIL (not closed)
- **UI filter behavior across all cards:** FAIL
- **Unexpected rows under active filters:** FAIL
- **Metric consistency for known scopes:** PASS

### Final Verdict (v1 Sign-off)
- **FAIL (v1 remains blocked pending successful, persisted filter mapping correction and repeat UI re-validation)**
