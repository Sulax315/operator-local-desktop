# Migration decisions

## 1. Keep / reuse (in this repo)

- **MCP edge pattern**: nginx + compose structure + env contract + runbooks + **auth_sidecar** (self-contained).
- **One host-nginx example**: same-origin split UI/API (from Action Desk origin file).
- **One compose example**: loopback-published three-tier pattern (Postgres + API + UI).
- **SQLite backup/restore scripts**: WorkOS-origin, as templates.
- **Env examples**: MCP gateway, Action Desk split env files, WorkOS production example.
- **Reference-only**: Control Tower deploy README + nginx tpl; profit-forensics architecture doc.

## 2. Archive

Move these **entire sibling directories** off the active workspace into a dated archive (tarball or `archive/YYYY-MM-DD/`) **after** you approve cleanup. They are **not** copied into this repo as codebases.

- `ControlTower`
- `mcp_gateway`
- `action-desk`
- `WorkOS`
- `profitintel-analytics-workspace`
- `ProfitIntel`
- `NotesSummary`
- `profit-forensics`
- `meeting_intelligence`
- `ScheduleLab`
- `ScheduleOS`
- `FinanceOS`
- Root `docs` (if still empty or non-essential)

## 3. Delete

After archive verification, **delete** from the active workspace:

- `ProfitIntel` (duplicate product track; archive the workspace copy only).
- `NotesSummary` (conflicting multi-app nginx and extra deploy tracks).
- `FinanceOS` (dev-default credentials; no salvage value beyond generic tutorials).
- `ScheduleOS` (charter/code mismatch; charter lives in archive if you keep it).
- Empty or junk top-level folders.

**Do not delete** until archive exists and someone has spot-checked the tarball.

## 4. Reference only

- `starter-assets/reference-only/*` is **not** for copy-paste into production without rewriting.
- Control Tower materials document a **specific** Python + systemd + `/srv` layout; your next stack may be container-first—use as a checklist, not a mandate.
- Profit-forensics architecture informs **data/ingest** design language only.

## 5. Non-negotiable rules for the clean repo

1. **No** resurrection of dead product names as folder roots in this repo (`ControlTower`, `ProfitIntel`, etc.) unless you intentionally reboot a product with a new charter.
2. **No** second nginx canon: one host pattern + one container-edge pattern is enough until a real requirement forces more.
3. **No** full git history migration from prototypes into this repo’s mainline—archive preserves history if needed.
4. **No** “interesting” code drops without a 30–60 day use case and a named owner.
5. **starter-assets/** stays **small**; new work grows in **new** top-level dirs with explicit scope.
