# Bratek Operator Stack — Master Plan

> **Program status:** Phases 1–3 **complete** (V4). **Phase 4 — ECharts Foundation** is **ACTIVE** (V5). Long-form governance: **`MASTER-PLAN-UPDATED-V5.txt`** (current phase + ECharts rules), **`MASTER-PLAN-UPDATED-V4.txt`** (Phases 1–3 lock-in). Continuity paste: **`docs/CONTINUITY_FOR_NEW_THREAD.md`** (update thread context when Phase 4 work proceeds).

## System identity

Snapshot-driven schedule intelligence: CSV → Postgres truth layer → SQL views/signals → **Metabase** (operational) and **ECharts** (projection-only additions). Guarded execution (`operator_run_snapshot_cycle.py`) orchestrates validated VM workflows **without** owning schedule semantics.

**Not:** Control Tower, a scheduling engine, PM/workflow platform, or an AI-first owner of schedule logic.

## Authoritative phase state

| Track | Scope | Status |
|-------|--------|--------|
| **Phase 1** | Snapshot truth layer: `schedule_tasks`, uniqueness, dual snapshots, SQL views | **Complete** |
| **Phase 2** | Metabase operator dashboard on Postgres signals | **Complete** |
| **Phase 2 ext** | Metabase REST automation (native SQL questions, dashboard wiring) | **Complete** |
| **Phase 3** | OpenClaw-aligned guarded wrapper + audit JSON | **Complete** |
| **Phase 4** | ECharts foundation: read-only API + operator charts from views only; Metabase stays on | **Active** |

*Infra:* Root `docker-compose.yml` is still the minimal operator plane (Postgres + Metabase + n8n + **operator ECharts** service on `127.0.0.1:8090`).

## Phase 4 rules (summary)

- ECharts and companion HTTP APIs are **projection-only**; Postgres views remain authoritative.
- **Do not** reimplement `v_signal_recently_slipped_tasks` (or other signal) rules in JS/Python.
- Metabase is **not** replaced; it remains the live operator BI surface in parallel.

## Key artifacts

| Purpose | Location |
|---------|----------|
| Guarded cycle | `scripts/operator_run_snapshot_cycle.py`, `docs/operator_run_snapshot_cycle_runbook.md` |
| Metabase publish | `scripts/publish_recently_slipped_metabase.py`, `docs/metabase_api_publish_runbook.md` |
| ECharts (first) | `web/operator_echarts/`, `docs/echarts_recently_slipped_runbook.md` |
| ECharts (second) | Critical path strip: `v_operator_critical_path_current`, `/critical-path`, `docs/echarts_critical_path_current_runbook.md` |
| Driver path (truth contract) | Spec only until export provides `path_sequence`: **`docs/driver_path_data_contract.md`** |
| SQL truth | `sql/01_schema.sql`, `sql/03_insert_schedule_tasks.sql`, `sql/04_signals.sql` |

## Next work (within Phase 4)

- Harden operator ECharts (auth, TLS termination via future edge) as governance requires.
- Additional read-only endpoints/charts **only** from existing or new SQL views — no truth migration.
