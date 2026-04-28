# Continuity — paste for a new ChatGPT thread

Copy everything inside the fence below into a new conversation when resuming operator-stack work.

```
You are continuing Bratek Operator Stack work.

Authoritative facts (live-proven, do not re-litigate as “pending”):
- PostgreSQL is the sole schedule/signal truth layer.
- Dual snapshots coexist in schedule_tasks; UNIQUE (snapshot_date, task_id).
- Views v_schedule_snapshot_pair_latest, v_schedule_task_finish_delta_latest_pair,
  v_signal_recently_slipped_tasks are deployed and used.
- Metabase API publisher (publish_recently_slipped_metabase.py) is live and idempotent.
- Guarded wrapper operator_run_snapshot_cycle.py is the first OpenClaw-ready
  execution target: validate-only, dry-run publish, and validate+publish have PASSED.
- Publisher env files may use KEY=value or export KEY=value lines.

Non-negotiables:
- No schedule logic in Metabase beyond native SQL pointing at Postgres views.
- No schedule logic reimplemented in Python wrappers.
- No browser automation for Metabase admin.
- ECharts (Phase 4) is projection-only from Postgres views — no signal logic in JS.
- No Control Tower scope.

Current phase lock-in:
- Phase 1 (truth layer), Phase 2 (dashboard), Phase 2 extension (MB automation),
  Phase 3 first execution target — COMPLETE.
- Phase 4 (ECharts foundation) — ACTIVE (projection-only; see MASTER-PLAN-UPDATED-V5.txt).

Next authorized direction:
- Phase 4: additional read-only ECharts/API surfaces from SQL views only.
- Expand the guarded execution layer with additional audited commands;
  preserve audit JSON, deterministic CLI, subprocess delegation to existing scripts.

Repo: /srv/operator-stack-clean
Governance: MASTER-PLAN-UPDATED-V5.txt (Phase 4), MASTER-PLAN-UPDATED-V4.txt (Phases 1–3)
ECharts runbook: docs/echarts_recently_slipped_runbook.md
Wrapper runbook: docs/operator_run_snapshot_cycle_runbook.md
```

Long-form governance: **`MASTER-PLAN-UPDATED-V5.txt`**, **`MASTER-PLAN-UPDATED-V4.txt`** (repo root).
