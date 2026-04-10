# Repository architecture (Clean Edition)

## Current scope: Phase 1 runnable stack

Phase 1 adds a **minimal operator plane** at the repo root:

| Service   | Role | Host exposure |
|-----------|------|----------------|
| `postgres` | Shared database for Metabase app DB and n8n | **None** (internal Docker network only) |
| `metabase` | BI / dashboards (you add data sources in UI) | `127.0.0.1:8082` → container `3000` |
| `n8n` | Workflow automation | `127.0.0.1:8083` → container `5678` |

**Persistence**

- Named volume `bratek-phase1-postgres-data` → Postgres data directory.
- Named volume `bratek-phase1-n8n-data` → n8n encryption keys and local state under `/home/node/.n8n`.
- On **first** Postgres init only, `docker/postgres/init/01-create-databases.sql` creates databases `metabase` and `n8n`.

**Port map (host)**

| Port | Service |
|------|---------|
| 8082 | Metabase |
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
├── docker-compose.yml       # Phase 1 — Metabase + n8n + Postgres
├── .env.example
├── docker/postgres/init/    # First-boot DB creation
├── docs/
├── scripts/
│   ├── smoke.sh             # Phase 1 smoke
│   ├── inventory_workspace.sh
│   ├── stage_archive_plan.sh
│   └── stage_delete_plan.sh
└── starter-assets/          # Reference snippets (not Phase 1 dependencies)
```

## Design rules

1. Phase 1 **must** run with only this repo—**no** dependency on archived prototype paths.
2. Do not merge `starter-assets` into Compose without an explicit design decision.
3. Secrets live in `.env` (gitignored), not in compose files.
