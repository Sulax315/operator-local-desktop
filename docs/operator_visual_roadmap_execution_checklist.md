# Operator Visual Roadmap - Execution Checklist

Purpose: turn the V1/V2 roadmap into ticket-sized implementation slices that can be delivered incrementally without breaking existing operator workflows.

## Phase 1 (In Progress) - Platform polish + trust signals

- [x] Add branded header strip across operator pages.
- [x] Move A3 Float Risk heading to HTML caption for readability.
- [x] Add standardized API metadata envelope (`generated_at_utc`, confidence, sources).
- [x] Render freshness/confidence badges on each page header from API metadata.
- [x] Add wow change-class waterfall dataset to executive payload and chart.
- [x] Add release notes entry in operator docs.

## V1 Quick Wins (1 week total)

### Day 1-2

- [x] **Ticket V1-01** - Metadata contract for all operator API endpoints
  - Backend: `web/operator_echarts/app.py`
  - Endpoints:
    - `/api/operator/recently-slipped-tasks`
    - `/api/operator/critical-path-current`
    - `/api/operator/computed-driver-path-current`
    - `/api/operator/path-comparison-current`
    - `/api/operator/executive-visuals`
  - Acceptance:
    - `metadata.generated_at_utc` present
    - `metadata.source_confidence` present (`authoritative_import`, `computed_projection`, `mixed_projection`)
    - `metadata.source_views` present as array

- [x] **Ticket V1-02** - Freshness/confidence badges on chart pages
  - Frontend:
    - `web/operator_echarts/static/index.html`
    - `web/operator_echarts/static/critical_path.html`
    - `web/operator_echarts/static/computed_path.html`
    - `web/operator_echarts/static/path_comparison.html`
    - `web/operator_echarts/static/executive_signals.html`
  - Acceptance:
    - Header shows confidence + generated timestamp + source count
    - Badges degrade gracefully when metadata is missing

- [x] **Ticket V1-03** - Exception funnel strip on Executive Signals
  - Backend: extend `/api/operator/executive-visuals` summary object
  - Frontend: add funnel card strip in `executive_signals.html`
  - Funnel:
    - compared rows
    - changed rows (non-unchanged)
    - critical-transition rows (`became_critical`)
    - P1 rows (from path comparison summary when available)

### Day 3-4

- [x] **Ticket V1-04** - Finish variance contributors waterfall
  - Backend:
    - Option A: extend `/api/operator/executive-visuals`
    - Option B: add `/api/operator/finish-variance-contributors`
  - SQL source:
    - `v_schedule_wow_change_class_waterfall`
    - `v_schedule_wow_task_delta_latest_pair`
  - Frontend:
    - add waterfall chart panel in `executive_signals.html`

- [x] **Ticket V1-05** - KPI trend sparkline contract
  - Backend: historical KPI endpoint or extension with last N snapshots
  - SQL source: add historical snapshot KPI view if latest-only view is insufficient
  - Frontend: tiny trend lines on KPI cards

- [x] **Ticket V1-06** - P1 aging histogram
  - Backend: `/api/operator/p1-aging`
  - SQL source: snapshot history from path-comparison classifications
  - Frontend: aging distribution panel + links to task drill-in

### Day 5

- [x] **Ticket V1-07** - UX polish pass + export hooks
  - Improve axis label readability and consistent legends
  - Add per-panel export (png/csv links)
  - Add status text for row caps and truncated datasets

- [x] **Ticket V1-08** - Validation + operator sign-off runbook
  - Add test checklist in docs
  - Verify endpoint payload shapes in smoke script
  - Capture before/after screenshots for operator training

## V2 Medium Scope (2-4 weeks)

- [ ] **Ticket V2-01** - Finish forecast cone (best/base/worst)
  - Endpoint: `/api/operator/finish-forecast-cone`
  - Sources: wow deltas + driver path history + confidence assumptions
  - Status: API endpoint implemented; executive heuristic cone panel wired

- [ ] **Ticket V2-02** - Driver path churn Sankey
  - Endpoint: `/api/operator/driver-path-churn`
  - Sources: historical computed path snapshots + path sequence transitions
  - Status: API endpoint implemented; executive panel wired (bar summary), Sankey variant pending

- [ ] **Ticket V2-03** - Owner/control-account impact matrix
  - Endpoint: `/api/operator/impact-by-owner`
  - Sources: wow delta + owner mapping dimensions
  - Status: API endpoint implemented (control_account owner proxy); executive panel wired

- [ ] **Ticket V2-04** - Dependency quality trend dashboard
  - Endpoint: `/api/operator/dependency-quality-trend`
  - Sources: path comparison quality fields across snapshots
  - Status: API endpoint implemented; executive trend panel wired

- [ ] **Ticket V2-05** - Daily change brief (auto narrative)
  - Endpoint: `/api/operator/daily-change-brief`
  - Sources: wow movement, P1 subtype shifts, critical transition deltas
  - Status: API endpoint implemented; executive-signals UI panel wired

- [ ] **Ticket V2-06** - Scenario impact sandbox (lightweight)
  - Endpoint: `/api/operator/scenario-impact`
  - Sources: driver path + finish delta model assumptions
  - Status: API endpoint implemented (heuristic aggregate projection); executive sandbox panel wired

## Definition of Done (for each ticket)

- [ ] Endpoint returns deterministic schema with null-safe fields.
- [ ] UI handles empty/error states without blank canvas.
- [ ] Row-cap behavior is disclosed in status text.
- [ ] Snapshot context shown in subtitle/meta.
- [ ] No linter errors in modified files.
- [ ] Smoke checked at:
  - `/`
  - `/critical-path`
  - `/computed-path`
  - `/path-comparison`
  - `/executive-signals`
