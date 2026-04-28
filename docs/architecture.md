# Repository architecture (Clean Edition)

## Operator program (live)

Beyond the Compose stack below, the **snapshot truth layer**, **multi-snapshot views**, **Metabase API publisher**, **first guarded execution wrapper** (`scripts/operator_run_snapshot_cycle.py`), and **Phase 4 ECharts** (`web/operator_echarts/`, loopback **8090**) are in scope. Governance: **`MASTER-PLAN-UPDATED-V5.txt`** (Phase 4 active), **`MASTER-PLAN-UPDATED-V4.txt`**. Continuity: **`docs/CONTINUITY_FOR_NEW_THREAD.md`**.

## Current scope: Phase 1 runnable stack (Compose / infra)

The root Compose file adds a **minimal operator plane** at the repo root:

| Service   | Role | Host exposure |
|-----------|------|----------------|
| `postgres` | Shared database for Metabase app DB and n8n | **None** (internal Docker network only) |
| `metabase` | BI / dashboards (you add data sources in UI) | `127.0.0.1:8082` → container `3000` |
| `operator_echarts` | Read-only FastAPI + ECharts pages: slipped tasks + critical tasks timeline (Postgres views only) | **`0.0.0.0:8090`** (host port 8090 on all interfaces; use firewall + SSH tunnel as appropriate) |
| `n8n` | Workflow automation | `127.0.0.1:8083` → container `5678` |

**Persistence**

- Named volume `bratek-phase1-postgres-data` → Postgres data directory.
- Named volume `bratek-phase1-n8n-data` → n8n encryption keys and local state under `/home/node/.n8n`.
- On **first** Postgres init only, `docker/postgres/init/01-create-databases.sql` creates databases `metabase` and `n8n`.

**Port map (host)**

| Port | Service |
|------|---------|
| 8082 | Metabase |
| 8090 | Operator ECharts (Phase 4); open `http://127.0.0.1:8090` locally or `http://<vm-ip>:8090` when bound to all interfaces |
| 8083 | n8n |

Postgres uses **5432** only inside the `phase1-internal` network.

## Phase 1 intentionally excludes

- nginx, TLS, domains, SSO
- OpenProject, custom Bratek app code, MCP gateway runtime
- Automated archive/delete of legacy sibling repos (handled outside this stack)
- Production backup/restore automation (add later)

## Salvage / starter assets (historical patterns)

The `starter-assets/` tree holds **extracted prototypes** (nginx examples, MCP edge reference, env templates). It is **not** wired into Phase 1 Compose. Use as copy-paste reference only.

```
operator-stack-clean/
├── docker-compose.yml       # Metabase + n8n + Postgres + operator ECharts
├── .env.example
├── docker/postgres/init/    # First-boot DB creation
├── docs/
├── web/
│   └── operator_echarts/    # Phase 4 — read-only API + ECharts page
├── scripts/
│   ├── smoke.sh             # Compose smoke
│   ├── inventory_workspace.sh
│   ├── stage_archive_plan.sh
│   └── stage_delete_plan.sh
└── starter-assets/          # Reference snippets (not Phase 1 dependencies)
```

## Design rules

1. Phase 1 **must** run with only this repo—**no** dependency on archived prototype paths.
2. Do not merge `starter-assets` into Compose without an explicit design decision.
3. Secrets live in `.env` (gitignored), not in compose files.
