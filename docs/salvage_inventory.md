# Salvage inventory

Structured record of assets extracted into this repo from the prototype workspace (`c:\Dev\` sibling trees). All paths below are **destination** paths inside **this** repository unless noted as “source”.

| Extracted asset | Original source path | Why useful | Intended future use | Confidence | Notes / caveats |
|-----------------|----------------------|------------|---------------------|------------|-----------------|
| `starter-assets/mcp-edge/docker-compose.yml` | `mcp_gateway/docker-compose.yml` | Complete pattern for TLS edge, health-gated `depends_on`, internal-only MCP services | Template for a future HTTPS MCP gateway or similar edge | **High** | **Not buildable as-is**: `build.context` points at MCP server Dockerfiles **not** included in this repo. Trim services or add your own images. |
| `starter-assets/mcp-edge/nginx/nginx.conf` + `nginx/conf.d/mcp_gateway.conf` | `mcp_gateway/nginx/` | `auth_request`, rate limits, path routing, TLS file layout | Adapt for any containerized nginx edge | **High** | Upstream names (`mcp_sample`, etc.) must match your compose service names. |
| `starter-assets/mcp-edge/.env.example` | `mcp_gateway/.env.example` | Bearer token, panel auth, TLS mount, host path overrides | Env contract for edge stack | **High** | Contains example hostnames; replace for greenfield. |
| `starter-assets/mcp-edge/runbooks/deploy.md` | `mcp_gateway/ops/runbooks/deploy.md` | Certbot/TLS, compose operations | Operator checklist | **High** | References old domain; process still valid. |
| `starter-assets/mcp-edge/runbooks/verification.md` | `mcp_gateway/ops/runbooks/verification.md` | Verification env vars and curl patterns | Post-deploy checks | **High** | |
| `starter-assets/mcp-edge/runbooks/rollback.md` | `mcp_gateway/ops/runbooks/rollback.md` | Failure recovery steps | Incident response | **High** | |
| `starter-assets/mcp-edge/auth_sidecar/*` | `mcp_gateway/services/auth_sidecar/` | Small FastAPI bearer verifier for `auth_request` | Reuse as-is or fork for API key validation at edge | **High** | Single file + Dockerfile; self-contained. |
| `starter-assets/nginx/example-split-ui-api-same-origin.conf` | `action-desk/infra/nginx/actiondesk.conf` | Host nginx: `/` + `/_next/` to UI, `/api/` to API, TLS snippets | Standard same-origin SPA + API behind one hostname | **High** | Still contains **example** `server_name` and cert paths from source; edit before use. |
| `starter-assets/compose/example-app-frontend-backend-postgres.loopback.yml` | `action-desk/infra/compose/docker-compose.yml` | Postgres + API + frontend with **127.0.0.1** publish for host nginx | Baseline for VM + host TLS + internal DB | **High** | **Does not include** Dockerfiles for backend/frontend; structural reference only unless you copy build contexts from archive. |
| `starter-assets/scripts/backup-workos-sqlite.sh` | `WorkOS/deploy/backup-workos-sqlite.sh` | Proven SQLite backup via running container | Any similar SQLite-in-container layout | **Medium** | Hardcodes `STACK_DIR`, `COMPOSE_FILE`, `docker-compose` invocation—**must adapt**. |
| `starter-assets/scripts/restore-workos-sqlite.sh` | `WorkOS/deploy/restore-workos-sqlite.sh` | Restore with pre-restore copy | Disaster recovery template | **Medium** | Same coupling; review paths. |
| `starter-assets/env/mcp-gateway.env.example` | `mcp_gateway/.env.example` (duplicate) | Central env folder collection | Quick scan of edge variables | **High** | Duplicate of `mcp-edge/.env.example` for folder convention. |
| `starter-assets/env/backend.env.example` | `action-desk/infra/env/backend.env.example` | API URL, DB URL pattern, CORS | Backend env shape | **High** | Product-specific names; rename vars in new apps. |
| `starter-assets/env/frontend.env.example` | `action-desk/infra/env/frontend.env.example` | Next.js runtime env | Frontend env shape | **High** | |
| `starter-assets/env/postgres.env.example` | `action-desk/infra/env/postgres.env.example` | Postgres user/db/password template | DB container env | **High** | |
| `starter-assets/env/workos-loopback-compose.env.example` | `WorkOS/deploy/env.production.example` | SQLite paths, backup dir, public URL, OAuth placeholders | Loopback compose + OAuth app registration pattern | **Medium** | WorkOS-specific variable names; use as pattern only. |
| `starter-assets/reference-only/controltower-deploy-pack-README.md` | `ControlTower/infra/deploy/controltower/README.md` | systemd + nginx + `/srv` layout for loopback Python | Reference when building non-container primary app on VM | **Medium** | **Do not treat as current production**; documentation only. |
| `starter-assets/reference-only/controltower-nginx-loopback-proxy.tpl` | `ControlTower/infra/deploy/controltower/templates/controltower-nginx.conf.tpl` | Parameterized TLS + `proxy_pass` to loopback | Template for single-backend sites | **High** | Placeholders `__DOMAIN__`, `__PORT__`, etc. |
| `starter-assets/reference-only/profit-forensics-architecture.md` | `profit-forensics/docs/architecture.md` | DuckDB runtime dirs, compose-level data flow | Ingestion / analytics bounded context | **Low–Medium** | **Reference only**; not extracted for immediate infra reuse. |

## Explicitly not extracted

- Full MCP server implementations (`sample_mcp`, `controltower_mcp`, …)—too product-coupled for a clean pack.
- Control Tower application source, ScheduleLab, meeting_intelligence code.
- NotesSummary aggregate nginx (conflicting routing)—**abandoned**, not copied.
- Second ProfitIntel tree—duplicate; not copied.
