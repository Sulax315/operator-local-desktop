# Metabase Operator Dashboard Spec - Productivity Loop (v1)

## Purpose
Provide an operator-first reporting surface that compares baseline productivity versus actual productivity by `project_code + scope_code`, using only validated Postgres truth-layer views.

This dashboard is projection-only:
- No authoritative formula logic is implemented in Metabase.
- All compute remains in SQL views (`sql/11_scope_productivity_views.sql`).

## Data Sources (Approved)
- `v_scope_baseline`
- `v_scope_actual`
- `v_scope_productivity`

No cards in this spec may source directly from Airtable or raw input tables as authoritative metric logic.

## Dashboard Name
`Operator Productivity Control Loop - v1`

## Global Filters
1. `project_code` (multi-select)
2. `scope_code` (multi-select, cascades after project filter if supported)
3. `variance_band` (UI-only helper filter over displayed `productivity_variance`, optional)

Filter defaults:
- `project_code`: all
- `scope_code`: all
- `variance_band`: all

## Cards

### Card 1 - Scope Productivity Leaderboard
- **Type:** table
- **Source view:** `v_scope_productivity`
- **Columns:** `project_code`, `scope_code`, `baseline_productivity`, `actual_productivity`, `productivity_variance`
- **Sort:** `productivity_variance` descending (highest positive variance at top)
- **Operator interpretation:**
  - Positive variance: producing above baseline rate.
  - Near-zero variance: tracking baseline.
  - Negative variance: under baseline rate (attention required).

### Card 2 - Under-Baseline Scopes
- **Type:** table
- **Source view:** `v_scope_productivity`
- **Filter in question:** `productivity_variance < 0`
- **Columns:** `project_code`, `scope_code`, `baseline_productivity`, `actual_productivity`, `productivity_variance`
- **Sort:** `productivity_variance` ascending (most negative first)
- **Operator interpretation:**
  - Prioritized action list for scopes falling behind baseline production rate.

### Card 3 - Baseline vs Actual Productivity (By Scope)
- **Type:** grouped bar chart
- **Source view:** `v_scope_productivity`
- **X-axis:** `scope_code`
- **Series:** `baseline_productivity`, `actual_productivity`
- **Breakout/series grouping:** optional by `project_code` when multiple projects selected
- **Sort:** `scope_code` ascending
- **Operator interpretation:**
  - Visual side-by-side comparison of planned versus achieved daily production rate.

### Card 4 - Baseline Context Table
- **Type:** table
- **Source view:** `v_scope_baseline`
- **Columns:** `project_code`, `scope_code`, `baseline_quantity`, `planned_install_days`, `baseline_productivity`
- **Sort:** `project_code`, then `scope_code`
- **Operator interpretation:**
  - Confirms planning assumptions that drive baseline rate.

### Card 5 - Actual Production Context Table
- **Type:** table
- **Source view:** `v_scope_actual`
- **Columns:** `project_code`, `scope_code`, `total_installed_quantity`, `actual_work_days`, `actual_productivity`
- **Sort:** `project_code`, then `scope_code`
- **Operator interpretation:**
  - Confirms realized installed quantities and work-day denominator used in actual rate.

## Operator Guardrails in Metabase
1. Do not recreate baseline/actual/variance formulas in GUI expressions.
2. Do not use Airtable-connected datasets for these cards.
3. Treat this dashboard as read/projection only.
4. If unit-governance gate fails (`sql/12_preload_unit_validation.sql` returns rows), pause interpretation for affected scopes until corrected.

## Expected Output Behavior
- Every scope row shown in `v_scope_productivity` should reconcile to:
  - `v_scope_baseline` baseline assumptions
  - `v_scope_actual` realized production totals
- Nulls indicate missing side of the join (baseline-only or actual-only scope) and should be flagged operationally.

## Build Sequence for Metabase Operator Surface
1. Connect Metabase to governed Postgres database.
2. Sync metadata for views:
   - `v_scope_baseline`
   - `v_scope_actual`
   - `v_scope_productivity`
3. Create cards exactly as specified above.
4. Add global filters and map to card fields.
5. Validate card outputs against latest evidence in `build_control/productivity_loop/phase1_validation_evidence.md`.

## Out of Scope for v1
- Labor productivity (`installed_quantity / labor_hours`)
- Automation-triggered alerts
- Cross-tool workflow orchestration
- Any logic shift from SQL truth layer into Metabase
