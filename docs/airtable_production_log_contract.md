# Airtable Production Log Contract (Phase 1)

## Contract Purpose
Define Airtable as controlled input UX only for production entries that are loaded into PostgreSQL, where authoritative logic is computed.

## Scope
- Phase: manual path validation
- Integration mode: manual export/import
- Authoritative compute layer: PostgreSQL only

## Airtable Base and Table Design
Base name: `Construction Productivity Input`  
Required tables:
1. `Scope Baseline Input`
2. `Production Log Input`
3. `Scope Task Map Input` (optional in first load, but contract-defined now)

## Required Fields
### 1) Scope Baseline Input
| Airtable Field | Type | Required | Rule |
|---|---|---|---|
| `project_code` | Single select | yes | Controlled list, no free text |
| `scope_code` | Single select | yes | Controlled list, no free text |
| `unit_code` | Single select | yes | Controlled list, no free text |
| `baseline_quantity` | Number | yes | `>= 0` |
| `planned_install_days` | Number | yes | `> 0` |
| `effective_date` | Date | yes | ISO date |
| `source_reference` | Single line text | yes | Export batch or row reference |
| `notes` | Long text | no | Non-authoritative annotation only |

### 2) Production Log Input
| Airtable Field | Type | Required | Rule |
|---|---|---|---|
| `project_code` | Single select | yes | Controlled list, no free text |
| `scope_code` | Single select | yes | Controlled list, no free text |
| `unit_code` | Single select | yes | Controlled list, no free text |
| `work_date` | Date | yes | ISO date |
| `installed_quantity` | Number | yes | `>= 0` |
| `source_reference` | Single line text | yes | Unique row/batch reference |
| `entry_user` | Single line text | no | Operator identifier |

### 3) Scope Task Map Input
| Airtable Field | Type | Required | Rule |
|---|---|---|---|
| `project_code` | Single select | yes | Controlled list, no free text |
| `scope_code` | Single select | yes | Controlled list, no free text |
| `task_code` | Single line text | yes | Controlled task identifier |
| `task_name` | Single line text | yes | Human-readable label |
| `effective_date` | Date | yes | ISO date |
| `active_flag` | Checkbox | yes | Active/inactive only |

## Allowed Values Strategy
- `project_code`, `scope_code`, and `unit_code` must be managed as controlled vocabularies.
- Maintain allowed values in a governed reference sheet (or Airtable select options) synchronized with SQL expectations.
- Disallow ad hoc free-text entry for controlled identifiers.

## Phase 1 Authoritative Unit Rules (Mandatory)
1. `unit_code` must come from the governed allowed list in `docs/productivity_unit_governance.md`.
2. For Phase 1 authoritative productivity comparison, each `project_code + scope_code` may have only one authoritative **physical** `unit_code`.
3. Mixed-unit rows for the same `project_code + scope_code` are invalid for authoritative comparison, even if all units are individually valid.
4. Proxy units (for example `activity_count`) must never be mixed with physical units within the same authoritative scope comparison.
5. When mixed-unit rows are detected, treat the dataset as an **input contract violation** and do not promote it to authoritative reporting.

## Source-to-Postgres Mapping
### Scope Baseline Input -> `scope_baseline`
- `project_code` -> `project_code`
- `scope_code` -> `scope_code`
- `unit_code` -> `unit_code`
- `baseline_quantity` -> `baseline_quantity`
- `planned_install_days` -> `planned_install_days`
- `effective_date` -> `effective_date`
- `source_reference` -> `source_reference`
- constant -> `source_system = 'manual_airtable_export'`
- `notes` -> `notes`

### Production Log Input -> `production_log`
- `project_code` -> `project_code`
- `scope_code` -> `scope_code`
- `unit_code` -> `unit_code`
- `work_date` -> `work_date`
- `installed_quantity` -> `installed_quantity`
- `source_reference` -> `source_reference`
- `entry_user` -> `entry_user`
- constant -> `source_system = 'manual_airtable_export'`

### Scope Task Map Input -> `scope_task_map`
- `project_code` -> `project_code`
- `scope_code` -> `scope_code`
- `task_code` -> `task_code`
- `task_name` -> `task_name`
- `effective_date` -> `effective_date`
- `active_flag` -> `active_flag`
- constant -> `source_system = 'manual_airtable_export'`

## Anti-Drift Rules
1. Airtable formulas are convenience only and never authoritative.
2. Any productivity calculation in Airtable must not be treated as source truth.
3. New identifiers cannot be introduced without governance approval.
4. Mapping changes require SQL and contract update in repo.
5. Metabase must consume Postgres views, not Airtable-derived calculations.
6. Unit governance violations (mixed units per `project_code + scope_code`) must block authoritative load/publish until corrected.

## Manual Export/Import Assumptions (Phase 1)
- Export from Airtable to CSV on a controlled cadence (daily or per shift batch).
- Validate headers and controlled values before import.
- Run pre-load unit validation (`sql/12_preload_unit_validation.sql`) before treating the load as authoritative.
- Load into PostgreSQL using reviewed SQL/import workflow.
- Run validation queries from runbook after each load.
- No API-based sync and no workflow automation in this phase.
