# Airtable Daily Entry Setup

## Purpose
Define the exact Airtable structure for daily field production entry before governed CSV import into PostgreSQL.

## Base and Table
- Base name: `Construction Productivity Input`
- Table name: `Production Log Daily Entry`

## Required Fields (Use Exact Names)
| Field name | Airtable type | Required | Guidance |
|---|---|---|---|
| `work_date` | Date | yes | Use ISO date (`YYYY-MM-DD`) |
| `project_code` | Single select | yes | Controlled project code (no free text) |
| `scope_code` | Single select | yes | Controlled scope code (no free text) |
| `unit_code` | Single select | yes | Must match governed unit for scope |
| `quantity_installed` | Number | yes | Non-negative quantity for the day |
| `entered_by` | Single line text | yes | Person who entered row |
| `notes` | Long text | no | Optional context only, non-authoritative |
| `source_record_id` | Single line text | yes | Unique row reference for traceability and dedupe |

## Allowed-Value Guidance
- `project_code`: select from active governed projects only (example: `WAVERLY`).
- `scope_code`: select canonical governed scope only (example: `structural_frame_p1_cfmf`).
- `unit_code`: use only governed values from `docs/productivity_unit_governance.md` (example: `lf`, `sf`, `ea`).
- For any `project_code + scope_code`, use one authoritative physical `unit_code`.
- Do not use free-text variants (for example `linear feet`, `L.F.`, or `frame_scope_1`).

## Data Entry Rules
1. Enter one row per scope worked per day.
2. Keep identifier spelling and casing consistent with governed lists.
3. `quantity_installed` must represent that day only (no running totals).
4. `source_record_id` must be unique and stable after entry (recommended format: `AT-YYYYMMDD-####`).
5. If a row is corrected, edit the existing record instead of creating near-duplicate rows.

## Example Daily Rows
| work_date | project_code | scope_code | unit_code | quantity_installed | entered_by | notes | source_record_id |
|---|---|---|---|---:|---|---|---|
| 2026-03-01 | WAVERLY | structural_frame_p1_cfmf | lf | 1850 | Jake | west wall run | AT-0001 |
| 2026-03-02 | WAVERLY | structural_frame_p1_cfmf | lf | 2120 | Jake | main bay framing | AT-0002 |
| 2026-03-03 | WAVERLY | structural_frame_p1_cfmf | lf | 1980 | Jake | punch + infill | AT-0003 |

## Export Contract
- Export this table to CSV with headers enabled.
- Do not rename columns before import.
- Preserve all rows intended for the load window.
