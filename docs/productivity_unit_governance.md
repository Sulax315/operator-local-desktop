# Productivity loop — unit governance

## Purpose

Define how `unit_code` is chosen and enforced so baseline productivity, actual productivity, and variance remain comparable and auditable. This document complements `docs/airtable_production_log_contract.md` and the productivity loop guardrails.

## Definitions

### physical_unit

A `unit_code` that measures **installed construction quantity in industry-standard dimensional or count units** directly tied to field measurement or material takeoff (for example linear feet of framing, square feet of membrane, each for counted assets).

Physical units answer: “How much **stuff** was installed?”

### proxy_unit

A `unit_code` that measures **progress surrogates** not equivalent to dimensional install quantity (for example `activity_count` for completed activities, story points, or percent-complete rolled into a scalar).

Proxy units answer: “How many **events** or **abstract slices** completed?” They must **not** be mixed with physical units in the same productivity comparison.

## Allowed unit codes (Phase 1)

Controlled vocabulary; extend only via governance change (Airtable selects + this doc + mapping notes).

| `unit_code` | Class | Meaning |
|-------------|-------|---------|
| `lf` | physical | Linear feet |
| `sf` | physical | Square feet |
| `sy` | physical | Square yards |
| `ea` | physical | Each (countable discrete units) |
| `cy` | physical | Cubic yards |
| `lb` | physical | Pounds (material weight) |
| `activity_count` | proxy | Count of completed activities or schedule milestones (not a substitute for `lf`/`sf`/etc.) |

## Core rule: matching governed physical units

**Baseline productivity and actual productivity may be compared only when:**

1. `scope_baseline` and `production_log` rows for the comparison share the same `project_code` and `scope_code`, and  
2. Both sides use the **same** `unit_code`, and  
3. That `unit_code` is a **physical_unit** (not a `proxy_unit`).

If baseline is captured in `lf` and production is logged in `sf` (or `ea`), **do not** compute variance until quantities are normalized in a governed way (separate scope rows, unit conversion table approved by governance, or re-entry in a single physical unit).

## Scope-to-unit mapping expectations

- Each **scope** has a **primary physical unit** agreed at baseline (for example cold-formed metal framing → `lf`, foundation waterproofing membrane → `sf`).
- `scope_task_map` may list multiple tasks under one scope; production log entries for that scope should still use the **scope primary physical unit** unless a deliberate secondary scope split exists (new `scope_code`, not ad hoc unit mixing).
- Airtable `unit_code` single-select options must stay aligned with this table.

## Valid vs invalid comparisons

### Valid

- Baseline: `project_code=WAVERLY`, `scope_code=structural_frame_p1_cfmf`, `unit_code=lf`, `baseline_quantity=9000`, `planned_install_days=15`  
- Production: same `project_code`, `scope_code`, `unit_code=lf`, daily `installed_quantity` in LF.  
- Variance from `v_scope_productivity` is meaningful **in LF per work day**.

### Invalid

- Baseline in `lf`, production in `activity_count` for the same `scope_code` → **invalid** (proxy vs physical).  
- Baseline in `sf`, production in `lf` without a governed conversion artifact → **invalid** (unit mismatch).  
- Same `scope_code` with two different physical units concurrently (for example some rows `lf`, some `sf`) → **invalid** until split into scopes or normalized.

## Relationship to SQL views

Current views (`sql/11_scope_productivity_views.sql`) aggregate by `project_code` + `scope_code` only. **They do not enforce unit equality in SQL.** Operational discipline and load validation must ensure a **single physical `unit_code` per project+scope** for Phase 1. If multi-unit scopes are required later, extend views with `unit_code` in `GROUP BY` via an approved schema change.

## Manual Phase 1 intake

Physical quantities typically arrive from takeoff (baseline) and superintendent/Airtable production rows (actual). Every row must carry a non-empty `source_reference` traceable to export batch, takeoff revision, or field ticket identifier.
