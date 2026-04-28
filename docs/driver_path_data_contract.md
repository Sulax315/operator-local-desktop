# Driver path — truth-layer data contract (Bratek Operator Stack)

**Status:** Contract **specified**; canonical view `**v_operator_driver_path_current` is not implemented** until import-authoritative sequencing exists (see §5). **Engine → Bratek export requirements** are normative in **§8**.

**Governance:** PostgreSQL is the sole truth layer (`MASTER-PLAN-UPDATED-V5.txt`). This document defines **what “driver path” means here**, what is **possible today**, what **must be added** before a driver-path relation can exist without guessing, and **exactly what the scheduling tool must export**.

---

## 1. Definition: “driver path” in this system

For this operator stack, a **driver path** (or **driving chain**) means:

- A **finite, ordered sequence** of tasks `(t₁, t₂, …, tₙ)` on a **single snapshot** that the **scheduling engine** (e.g. Asta Powerproject) considers the **driving / logic path** to a scope boundary (often project finish or a selected milestone).
- The order `**path_sequence = 1..n` is authoritative**: it must come from the **tool export** (or from a **fully specified** engine-side extract), not from heuristics in Postgres, Python, or JavaScript.

**What it is not**

- Not the same as “all critical tasks” (`critical` flag + incomplete).
- Not the same as “sort by finish date” or “low float first” heuristics.
- Not a **dependency graph** layout or **Gantt** surface (out of scope for this document).
- Not **parsing** `predecessors` / `successors` **text** in application code to invent edges.

---

## 2. Available truth today (`schedule_tasks`)

Relevant columns (from `sql/01_schema.sql` and load `sql/03_insert_schedule_tasks.sql`):


| Column                                           | Role                                                                                 |
| ------------------------------------------------ | ------------------------------------------------------------------------------------ |
| `snapshot_date`, `task_id`, `task_name`          | Identity on a load                                                                   |
| `start_date`, `finish_date`, `early_*`, `late_*` | Dates from export                                                                    |
| `total_float_days`, `free_float_days`            | Numeric float from export                                                            |
| `critical`                                       | Import’s critical flag (text)                                                        |
| `predecessors`, `successors`                     | **Opaque text** copied from CSV (`NULLIF(TRIM(...))`) — **no** normalized edge table |
| `critical_path_drag_days`                        | Numeric from export                                                                  |
| `percent_complete`                               | Progress                                                                             |


`**v_operator_critical_path_current`** (`sql/04_signals.sql`): critical-flag, incomplete, current snapshot — **explicitly not** a validated driving chain; ordering there is **presentation-only** (finish / start / `task_id`).

---

## 3. Feasibility — can a true driver path be built **now**?

### 3.1 From existing fields alone?

**No — not as an authoritative driver path.**

Reasons:

1. **No `path_sequence` (or equivalent)** is loaded into `schedule_tasks` or any other table in this repo.
2. `**predecessors` / `successors` are free-form text** from the CSV. Real exports can contain commas inside task names, multiple ID conventions, lag/lead notation (depending on tool/settings), etc. There is **no** checked-in, versioned **grammar spec** binding those strings to `task_id` edges for this stack.
3. **SQL-derived topology** (recursive CTE over guessed edges) would still **not** equal the engine’s **driving path** unless the walk rules and edge semantics are exactly those of the scheduler — that is **engine logic**, not something this repo can claim from floats + critical alone.
4. **Heuristics** (“zero float”, “critical first”, topological sort) are **not** an auditable substitute for the tool’s driving chain.

### 3.2 Additional data required from Asta (or other engine) export?

**Yes.** At minimum, the export (or a sidecar file produced in the same job) must supply **ordered path membership** in a way that maps 1:1 to `task_id` on the same `snapshot_date` / load.

---

## 4. Strategy chosen: **C — not currently possible** (blocked until **A**)


| Option                            | Verdict                                                                                                                                                                 |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Import-authoritative path** | **Required** for a real `path_sequence`. Preferred once export (or ETL) provides it.                                                                                    |
| **B — SQL-derived path**          | **Rejected for “driver path”** in this stack: would require undocumented pred/succ parsing + graph rules that duplicate CPM/driving semantics without engine guarantee. |
| **C — Not currently possible**    | **Selected today.** No `v_operator_driver_path_current` view is created to avoid a **fake** driver chain.                                                               |


---

## 5. Target data contract (Postgres) — **when Option A is satisfied**

### 5.1 Relation name

`v_operator_driver_path_current` (or a base table `driver_path_tasks` materialized per load — physical design is an implementation detail; the **contract** is the column set below.)

### 5.2 Required columns (minimum)


| Column             | Type      | Source                                             | Notes                                                                       |
| ------------------ | --------- | -------------------------------------------------- | --------------------------------------------------------------------------- |
| `path_sequence`    | `integer` | **Export / engine extract**                        | **Required.** Strictly increasing 1…N along the path.                       |
| `snapshot_date`    | `date`    | Same as `schedule_tasks.snapshot_date` for the row | Current snapshot scope.                                                     |
| `task_id`          | `text`    | Export                                             | Must match `schedule_tasks.task_id` for join validation.                    |
| `task_name`        | `text`    | Export or join from `schedule_tasks`               | Join is OK if name is not duplicated in export path table.                  |
| `start_date`       | `date`    | `schedule_tasks` or export                         |                                                                             |
| `finish_date`      | `date`    | `schedule_tasks` or export                         |                                                                             |
| `total_float_days` | `numeric` | `schedule_tasks`                                   | Authoritative float from import.                                            |
| `critical`         | `text`    | `schedule_tasks`                                   | Import flag.                                                                |
| `predecessors`     | `text`    | `schedule_tasks`                                   | **Pass-through only** in this view; no parsing in consumers for path logic. |
| `successors`       | `text`    | `schedule_tasks`                                   | Same.                                                                       |
| `path_scope`       | `text`    | Export optional                                    | e.g. `project_finish`, milestone id — if export provides it.                |
| `path_source`      | `text`    | ETL constant                                       | e.g. `asta_export_vX` for auditability.                                     |


### 5.3 Example ways to supply Option A (non-exhaustive)

Normative column names, file formats, staging/target tables, and validation/failure rules are in **§8**. At a high level:

1. **Dedicated CSV or JSON file** from the engine (recommended): one row per `(path_sequence, task_id, …)` per `path_scope`, loaded into `**schedule_driver_path_staging` → `schedule_driver_path`** (§8.3).
2. **Official API / report** from the scheduling tool that emits the same logical fields — ingested with the same `snapshot_date` as `schedule_tasks`.
3. **Extra columns on the existing task CSV** are **discouraged** unless every task row carries authoritative `path_sequence`/`path_scope` from the engine (wide rows complicate quoting and are harder to validate than a sidecar file).

Until §8 is satisfied in production loads, **do not** ship a view that implies `path_sequence` is engine-authoritative.

---

## 6. Validation method (once data exists)

Formal rules live in **§8.4** (ingestion / QA). Summary:

1. **Row-level:** For a fixed `snapshot_date`, `path_scope`, and `run_id`, `path_sequence` is contiguous unless the export contract explicitly allows gaps; sequence and task keys are unique as in §8.4.
2. **Referential:** Every `(snapshot_date, task_id)` in the driver-path dataset exists in `schedule_tasks` for that snapshot (or violations reported in a QA view).
3. **Provenance:** `path_source`, `run_id`, and export file hash / `load_label` stored for audit (pattern already used on `schedule_tasks.load_label`).
4. **Engine cross-check:** Spot-check in the scheduling tool UI: driving path task order matches `ORDER BY path_sequence` in Postgres for the same `path_scope`.

---

## 7. Limitations (current)

- **No** canonical driver-path dataset in Postgres today.
- `**v_operator_critical_path_current`** remains the **critical incomplete** slice; it must **not** be labeled a driver path in UI or docs.
- **Option B** remains unsuitable as **authoritative driver path** without a signed specification from the scheduling tool vendor + validated parser — out of scope for “truth without guessing.”
- **Visualization** (ECharts, Metabase) must only attach after this contract is implemented; until then, any “driver path” chart would violate the no-fake-path rule.

---

## 8. Export contract (scheduling engine → Bratek)

This section defines **exactly** what Asta Powerproject (or another CPM engine) must **export** so Postgres can hold an **authoritative** driver path. **Path order never comes from** `predecessors` / `successors` **text**, heuristics, or application code.

### 8.1 Required export fields (minimum)

Every row in the driver-path export describes **one position** on **one** engine-defined path for **one** snapshot scope.


| #   | Field           | Required | SQL-ish type                        | Semantics                                                                                                                                                                                        |
| --- | --------------- | -------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | `path_sequence` | **Yes**  | `integer`                           | **1 = upstream end of path as defined by the tool export**; strictly increasing along the path. Engine is sole authority for meaning of “upstream”.                                              |
| 2   | `task_id`       | **Yes**  | `text`                              | **Must byte-match** `schedule_tasks.task_id` for the same project after TRIM (same identifier the schedule CSV already uses — e.g. Asta “Task ID” column).                                       |
| 3   | `snapshot_date` | **Yes**  | `date` `YYYY-MM-DD`                 | **Must equal** the `snapshot_date` of the `schedule_tasks` load this path describes (same calendar date as `__BRA_SNAPSHOT__` in `sql/03_insert_schedule_tasks.sql`).                            |
| 4   | `path_scope`    | **Yes**  | `text`                              | Stable key for *which* driving path this is when multiple exist (e.g. `project_finish`, `milestone:<internal_id>`, `longest_path`). Tool-defined string; must be documented per project/program. |
| 5   | `start_date`    | **Yes**  | `date` `YYYY-MM-DD`                 | Task start on that path row (engine calendar).                                                                                                                                                   |
| 6   | `finish_date`   | **Yes**  | `date` `YYYY-MM-DD`                 | Task finish on that path row.                                                                                                                                                                    |
| 7   | `total_float`   | **Yes**  | `numeric` (or `text` + parse rules) | Total float as computed by the **engine** for that task at export time (same meaning as schedule export). May mirror `schedule_tasks.total_float_days` after join.                               |
| 8   | `critical`      | **Yes**  | `text`                              | Engine’s critical/driving flag for that task at export (same vocabulary family as existing `critical` column, e.g. `TRUE`/`FALSE`).                                                              |


**Strongly recommended (audit / ops)**


| Field                  | Required    | Type                   | Semantics                                                                                                       |
| ---------------------- | ----------- | ---------------------- | --------------------------------------------------------------------------------------------------------------- |
| `path_source`          | Recommended | `text`                 | Constant naming export pipeline, e.g. `asta_powerproject_driver_path_v1`.                                       |
| `run_id`               | Recommended | `text` (UUID)          | Unique id for **this** export run; ties path file to `schedule_tasks.load_label` / file hash in operator audit. |
| `export_timestamp_utc` | Recommended | `timestamptz` ISO 8601 | When the engine produced the path extract.                                                                      |
| `tool_name`            | Recommended | `text`                 | e.g. `Asta Powerproject`.                                                                                       |
| `tool_version`         | Recommended | `text`                 | Build or version string from the tool.                                                                          |
| `project_id`           | Optional    | `text`                 | Program/project identifier in the tool.                                                                         |
| `source_filename`      | Optional    | `text`                 | Original export filename.                                                                                       |
| `source_file_sha256`   | Optional    | `text`                 | Hex digest of file bytes for tamper-evident audit.                                                              |


**Naming convention (export files)**

- Header row: **exact** logical names below (CSV) or JSON keys in **snake_case** as specified.
- `task_id`: no leading/trailing spaces; must remain stable across schedule + path exports from the same snapshot job.

### 8.2 Export format specification

#### Option A — CSV (UTF-8)

- **Encoding:** UTF-8 with BOM optional; newline `\n` or `\r\n`.
- **First row:** header with column names **exactly** as listed (order may vary if loader maps by header name).
- **Delimiter:** comma. Fields containing comma, quote, or newline **must** be RFC 4180–quoted (`"` doubled inside quoted field).
- **Dates:** `YYYY-MM-DD` **preferred**; if the tool emits `MM/DD/YYYY` only, the **ingestion contract** must declare that explicitly and use one format per file (no mixing).

**Canonical minimum header (example)**

```text
path_sequence,task_id,snapshot_date,path_scope,start_date,finish_date,total_float,critical
```

**Recommended extended header**

```text
path_sequence,task_id,snapshot_date,path_scope,start_date,finish_date,total_float,critical,path_source,run_id,export_timestamp_utc,tool_name,tool_version
```

**Row constraints**

- `path_sequence`: integer ≥ 1; **globally unique per row** within `(snapshot_date, path_scope, run_id)` together with `task_id` uniqueness (see §8.4).
- `task_id`: non-empty after TRIM.
- `snapshot_date`: valid calendar date.
- `path_scope`: non-empty after TRIM.
- `total_float`: numeric acceptable to Postgres `numeric` after stripping unit suffixes **only if** the export contract documents allowed suffixes (e.g. `0d` → document strip rule in ingestion spec — **not** in this truth doc’s SQL). Prefer bare number in export.
- `critical`: non-empty recommended; if empty, ingestion treats as **validation failure** unless a default is explicitly allowed by program governance.

#### Option B — JSON (newline-delimited JSON optional)

- **Root:** array of objects **or** NDJSON (one object per line).
- **Keys:** snake_case, same logical names as CSV columns.
- **Types:** JSON numbers for `path_sequence` and `total_float`; ISO date strings `YYYY-MM-DD` for dates; strings for ids and flags.

**Minimal example (two tasks)**

```json
[
  {
    "path_sequence": 1,
    "task_id": "35465",
    "snapshot_date": "2026-04-09",
    "path_scope": "project_finish",
    "start_date": "2025-10-23",
    "finish_date": "2025-10-23",
    "total_float": 0,
    "critical": "FALSE",
    "path_source": "asta_powerproject_driver_path_v1",
    "run_id": "7f2c9b1e-4d3a-4b1e-9c0d-1234567890ab"
  },
  {
    "path_sequence": 2,
    "task_id": "35407",
    "snapshot_date": "2026-04-09",
    "path_scope": "project_finish",
    "start_date": "2025-06-18",
    "finish_date": "2025-08-14",
    "total_float": 0,
    "critical": "FALSE"
  }
]
```

### 8.3 Ingestion design (target architecture — not implemented here)

**Principle:** Staging accepts raw engine output; a **typed** table (or materialized load) holds promoted truth; `**schedule_tasks` remains the task register** for the snapshot. Driver path is a **separate relation** keyed by snapshot + scope + run, not a reinterpretation of `predecessors` text.


| Stage          | Suggested object                          | Role                                                                                                                                                                                                                                                                                           |
| -------------- | ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Raw landing    | `schedule_driver_path_staging`            | Mirror CSV/JSON columns as `text` (or minimal types); one row per path position; includes `run_id`, `load_label` echo.                                                                                                                                                                         |
| Promoted truth | `schedule_driver_path`                    | Typed columns: `snapshot_date`, `path_scope`, `run_id`, `path_sequence`, `task_id`, dates, `total_float_days`, `critical`, metadata; **PK** e.g. `(snapshot_date, path_scope, run_id, path_sequence)` **or** `(snapshot_date, path_scope, run_id, task_id)` per product choice (document one). |
| Join / view    | `v_operator_driver_path_current` (future) | Filter to **current** snapshot + **canonical** `path_scope` + latest `run_id` per governance rules.                                                                                                                                                                                            |


**Snapshot alignment**

- `schedule_driver_path.snapshot_date` **must equal** `schedule_tasks.snapshot_date` for every joined `task_id` validated for that load.
- **Load order:** Promote `schedule_tasks` for `(snapshot_date, load_label)` **first**; then ingest driver path with **same** `snapshot_date` and a `run_id` recorded in operator audit JSON alongside the schedule file.

**Relationship to `schedule_tasks`**

- **Foreign consistency:** Every `(snapshot_date, task_id)` in `schedule_driver_path` **must** exist in `schedule_tasks` for that `snapshot_date` (validation; optional `DEFERRABLE` FK in implementation phase).
- **Attributes:** Dates and float on the path export **may** duplicate `schedule_tasks`; on conflict, **policy must be declared** (e.g. “path export wins for dates on path rows” or “schedule_tasks wins — path export dates are QA-only”). Default recommendation: **schedule_tasks wins** for dates/float if both present; path export supplies **order** + scope; mismatches surface as **validation failures**.

### 8.4 Validation rules (ingestion / QA)

For each `(snapshot_date, path_scope, run_id)` group:

1. `**path_sequence` contiguous:** `MIN(path_sequence) = 1` and `COUNT(DISTINCT path_sequence) = MAX(path_sequence)` (no gaps) **unless** the export contract explicitly allows gaps and documents meaning.
2. **Unique sequence:** `(snapshot_date, path_scope, run_id, path_sequence)` is unique.
3. **Unique task per path (simple chain):** `(snapshot_date, path_scope, run_id, task_id)` is unique — **no duplicate** `task_id` on the same path instance.
4. **Referential:** Every `task_id` exists in `schedule_tasks` for that `snapshot_date`.
5. **Snapshot match:** `snapshot_date` is one of the distinct `schedule_tasks.snapshot_date` values already loaded (typically the **current** snapshot for operator views).
6. **Row count sanity:** `COUNT(*) ≥ 1` if a path is claimed; empty files rejected.
7. **Metadata:** If `run_id` is required by program policy, reject rows without it.

### 8.5 Failure modes


| Failure                        | Definition                                                                       | Handling (contract-level)                                                                                                     |
| ------------------------------ | -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **Missing `path_sequence`**    | Any row lacks integer sequence                                                   | **Reject entire file** for that `(path_scope, run_id)`; do not partially load.                                                |
| **Mismatched `task_id`**       | `task_id` not found in `schedule_tasks` for `snapshot_date`                      | **Reject** those rows and fail the load **or** quarantine in staging QA table — program must pick one; default **fail load**. |
| **Partial export**             | Gaps in `path_sequence`, or truncated file vs declared row count                 | **Reject**; require re-export from engine.                                                                                    |
| **Multiple conflicting paths** | Same `(snapshot_date, run_id)` but **different** orderings for same `path_scope` | **Reject** duplicate submissions; `path_scope` must disambiguate paths.                                                       |
| **Ambiguous `path_scope`**     | Empty `path_scope` while engine can emit multiple driving paths                  | **Reject**; exporter must set scope key.                                                                                      |
| **Date / float mismatch**      | Path row dates differ from `schedule_tasks` beyond declared tolerance            | **Warning or reject** per policy; never silently overwrite without rule.                                                      |
| **Wrong snapshot_date**        | Path file dated for snapshot not yet loaded                                      | **Reject**; align export job with schedule load.                                                                              |


### 8.6 Asta-specific note (non-binding; for export authors)

Asta (or vendor docs) may name reports “Longest path”, “Driving path”, etc. The **Bratek contract** does not mandate a menu item — it mandates **columns in §8.1** with values **computed by Asta**, not reconstructed in Bratek. If Asta exposes multiple path types, each must map to a distinct `path_scope` value agreed with operators.

---

## 9. Related files

- Schema: `sql/01_schema.sql`
- Schedule load: `sql/03_insert_schedule_tasks.sql`
- Signals (critical slice, not driver path): `sql/04_signals.sql`
- Operator projection (not truth definition): `web/operator_echarts/app.py`, `web/operator_echarts/static/critical_path.html`
- Critical-tasks runbook: `docs/echarts_critical_path_current_runbook.md`
- Sample exports (current **lack** driver-path columns): `data/*.csv`

