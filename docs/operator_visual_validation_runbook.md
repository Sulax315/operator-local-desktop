# Operator Visual Validation Runbook

Purpose: quick validation flow after dashboard/API changes so operators can trust visuals before daily use.

## Preconditions

- Docker stack is up (`postgres`, `operator_echarts`).
- Latest SQL view set is applied (including `17_schedule_wow_signals.sql`).
- Browser can reach the service URL used by operator team.

## Automated smoke check

Run from repo root:

```bash
./scripts/smoke.sh
```

Smoke waits for **`/api/health/ready`** (Postgres readiness) before hitting pages and APIs. Liveness-only checks use **`/api/health`**.

Expected:

- HTTP success for all operator pages:
  - `/`
  - `/critical-path`
  - `/computed-path`
  - `/path-comparison`
  - `/executive-signals`
- API success for:
  - `/api/operator/executive-visuals`
  - `/api/operator/p1-aging`
  - `/api/operator/daily-change-brief`
  - `/api/operator/driver-path-churn`
  - `/api/operator/impact-by-owner`
  - `/api/operator/dependency-quality-trend`
  - `/api/operator/finish-forecast-cone`
  - `/api/operator/scenario-impact`
- Contract checks present (see `scripts/smoke.sh` for the live list), including:
  - Executive: `metadata.generated_at_utc`, `metadata.source_confidence`, `kpi_history.rows`, `exception_funnel.p1_task_count`, `change_class_waterfall.rows`
  - Driver churn: `transition_flow.links`, `transition_flow.nodes`, `transition_flow.bucket_definition`
  - Owner matrix: `matrix.cells`, `matrix_task_index`
  - Dependency quality: `normalization_basis`
  - Finish cone: `points`, `historical_basis.cone_band_model`
  - Scenario: `scenario.adjusted_net_finish_delta_days`
  - P1 aging: `bucket_counts`
- Optional CI split: `OPERATOR_SMOKE_HEALTH_ONLY=1` runs compose config + operator `/api/health` wait only.

## Manual visual checklist (5-10 min)

### 1) Executive Signals page

- Brand strip renders at top.
- Metadata badges show confidence + generated timestamp + source count.
- KPI cards show values and sparklines (if historical pairs available).
- Exception funnel renders compared -> changed -> became critical -> P1.
- B2 waterfall renders with positive/negative finish delta bars.
- Panel action buttons work:
  - `Fullscreen`
  - `PNG` export
  - `CSV` export
- V2 executive panels (when data exists):
  - **Driver path churn:** Sankey vs bar toggle; drill to path comparison from task-driven rows.
  - **Owner impact matrix:** slice (phase vs area) and color metric; heatmap or rollup fallback; cell drill respects task index cap.
  - **Dependency quality trend:** rates per 100 tasks; subtitle reflects normalization basis.
  - **Finish forecast cone:** subtitle mentions historical stdev when `historical_basis.cone_band_model` is `heuristic_plus_history`.
  - **Scenario sandbox:** presets including KPI-aligned slipped and pulled-in counts; state persists under `operator_echarts_scenario_sandbox_v1` (impacted count, recovery days, `preset_id`).

### Metabase / SQL tile alignment (executive V2)

Use these JSON shapes when mirroring operator tiles or documenting questions (HTTP source or ETL into Metabase):

| Operator endpoint | Useful fields for tiles |
| --- | --- |
| `driver-path-churn` | `transition_flow.nodes`, `transition_flow.links`, `transition_flow.bucket_definition`, `transition_counts`, `rows` |
| `impact-by-owner` | `matrix.default_slice`, `matrix.default_metric`, `matrix.cells`, `matrix_task_index`, `rows` |
| `dependency-quality-trend` | `rows` (per-snapshot rates), `normalization_basis` |
| `finish-forecast-cone` | `points[]` (horizon, best/base/worst variance days), `inputs`, `historical_basis` |
| `scenario-impact` | `scenario.adjusted_net_finish_delta_days`, `baseline`, `inputs` |

### 2) Path Comparison page

- Metadata badges render under status row.
- P1 triage section loads.
- P1 aging section loads:
  - bucket bars visible
  - oldest P1 rows table visible
  - drill-in links navigate to task-specific pages

### 3) Other pages

- Recently Slipped, Critical Path, Computed Path all show metadata badges.
- No blank-screen regressions.

## Known caveats

- KPI sparklines depend on available distinct snapshot dates; if only one pair exists, trend line appears flat/short.
- P1 aging uses `snapshot_date - start_date` for current P1 projection rows (not cross-snapshot persistence age).
- Dashboard pages are served from containerized static bundle; rebuild required after frontend changes:

```bash
docker compose up -d --build operator_echarts
```

## Sign-off template

- Build hash / date:
- Smoke result:
- Manual validation reviewer:
- Issues found:
- Go/no-go:
