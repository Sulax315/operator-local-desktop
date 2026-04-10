# Architecture — Profit Forensics (Phase 2)

## High level

```
Browser (Next.js) ──HTTP──► FastAPI ──► DuckDB (file on disk)
                                │
                                ├── Runtime dirs (runtime / archive / exports)
                                ├── ops/parser_mappings (sheet alias YAML)
                                └── ops/diagnostics (bulk coverage artifacts)
```

Imports are **synchronous**: a POST with a **server-local** filesystem path triggers hash, copy-to-archive, fingerprint, `raw.*` registry writes, **canonical extraction**, staging inserts, core snapshot projection, and parser events.

## Backend modules

| Area | Responsibility |
|------|------------------|
| `core/` | Settings from environment; ensure runtime directories exist. |
| `db/` | DuckDB connection; `bootstrap.apply_all_ddl` applies `ddl/raw.sql`, `staging.sql`, `core.sql` in order. |
| `parsers/` | openpyxl load (fingerprint vs extraction `data_only`), filename inference, YAML rules, **JTD/labor/PCO extractors**, header and totals heuristics, cost-code normalization. |
| `validation/` | Pandera schemas for extracted frames. |
| `services/` | Fingerprinting, sheet classification, registry writes, **extraction orchestration**, report-version ids, coverage artifact writer. |
| `api/` | Health, diagnostics, projects (+ timeline), reports (+ import, coverage, per-workbook extraction summary). |
| `schemas/` | Pydantic request/response models. |

## Data model

### `raw` (ingestion)

- **`raw.workbook_registry`** — One row per imported workbook (id from file hash + original filename). Inferred `project_id`, `report_type`, `report_period_date`, structure hashes, archive path.
- **`raw.workbook_sheet_registry`** — Sheet extents, fingerprint metrics, **`section_alias`** from YAML (`jtd`, `labor`, `pco`, `detail`, `month_compare`, `profit_summary`, `unknown`).
- **`raw.parser_events`** — Deterministic `event_id`; includes `workbook_imported`, **`extraction_validation_failed`**, **`extraction_validation_warning`**, **`extraction_completed`**.

### `staging` (extracted lines)

All rows carry: `workbook_id`, `project_id`, `report_period_date`, `source_sheet_name`, `source_row_number`, `is_total_row`, **`lineage_hash`**, and section-specific measures.

- **`staging.jtd_rows`** — Job-to-date style cost lines (`cost_code_*`, budget / spent / commitment / forecast columns).
- **`staging.labor_rows`** — Labor category, hours, costs, forecasts.
- **`staging.pco_rows`** — PCO identifiers, status, description, amounts, impacts.

### `core` (analytical facts)

- **`core.report_versions`** — One row per imported workbook. **`report_version_id`** is deterministic from `workbook_id`, `project_id`, `report_type`, `report_period_date`, and a revised flag (filename contains `revised`). Includes **`workbook_id`** (unique) for provenance back to `raw` (extension beyond the minimal column list in the charter, required for operational joins).
- **`core.cost_snapshot`** — Projected from **non-total** JTD rows; preserves cost code, description, monetary fields, provenance columns.
- **`core.labor_snapshot`** — Non-total labor rows.
- **`core.pco_snapshot`** — Non-total PCO rows.

**Totals / subtotals** are detected via text heuristics (`total`, `subtotal`, `grand total`, …). Such rows may appear in **staging** (`is_total_row = true`) but are **never** inserted into core snapshot tables.

## Extraction flow

1. **Gate**: only sheets whose `section_alias` is `jtd`, `labor`, or `pco` are parsed.
2. **Header row**: first ~40 rows scored against section-specific header token patterns; best row above a minimum score wins.
3. **Column mapping**: normalized header text mapped to canonical fields (synonyms for budget, spent, PCO #, etc.).
4. **Typing**: currency/accounting numbers parsed deterministically (`$`, commas, parentheses negatives).
5. **Cost codes**: normalized to `NN-NNN` when a clear `phase-body` pair is present (`cost_code.py`).
6. **Validation**: Pandera validates each section’s frame; failures emit `extraction_validation_failed` with error list; extractor-level issues (e.g. header not found) emit `extraction_validation_warning`.
7. **Persist**: assign deterministic `extracted_row_id`; insert staging; insert `core.report_versions`; project facts to core snapshots (excluding totals).

## Frontend

Next.js App Router. Server components call same-origin `/api/diagnostics`; `next.config.ts` rewrites to the API origin (`INTERNAL_API_ORIGIN` in Docker). No hidden business logic: Phase 2 adds only API routes for coverage/timeline as needed for thin projections.

## Deployment

Docker Compose provides `api` and `web` services with mounted volumes for `./data`, `./shared`, and `./ops`. A host nginx reverse proxy terminates TLS and routes traffic to `web` (and optionally `/api` to `api`).

## Known unsupported / fragile patterns

- Sheets that **never** match alias rules (`unknown`) are skipped entirely.
- **Non-tabular** layouts (merged title blocks, pivots without a single header band) may fail header detection → warnings and zero rows for that sheet.
- **Labor / PCO** templates that use uncommon column labels may map incompletely until rules are extended.
- **Duplicate sheet names** are addressed by name when opening worksheets; ambiguous workbooks should be normalized upstream.
