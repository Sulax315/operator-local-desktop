# Bratek Operator Stack (Clean Edition)

Clean foundation for Bratek **operator infrastructure**: salvaged patterns plus a **Phase 1** runnable Docker stack (Metabase + n8n + Postgres) for local use.

## What this repo is

- **Phase 1 (root `docker-compose.yml`)** — loopback-only BI + workflow tools backed by Postgres.
- **`starter-assets/`** — small extracted files from retired prototypes (nginx/compose/MCP edge **examples** only; not auto-wired).
- **`docs/`** — architecture, deployment, migration decisions, salvage inventory, workspace audit snapshot.
- **`scripts/`** — Phase 1 smoke test; workspace inventory / archive-delete **dry-run** planners (no destructive actions inside the scripts).

## What Phase 1 includes

- **Postgres 16** (internal-only; no host port).
- **Metabase** at `http://127.0.0.1:8082`.
- **n8n** at `http://127.0.0.1:8083`.
- Named Docker volumes for Postgres and n8n data.

## Quick start (Phase 1)

```bash
cp .env.example .env
# Edit .env — set passwords

docker compose up -d
# After services are healthy:
bash scripts/smoke.sh
```

Full steps: **`docs/deployment.md`**. Architecture and boundaries: **`docs/architecture.md`**.

## What is intentionally deferred

- TLS, nginx, public hostnames
- OpenProject, SSO, MCP production edge
- Wiring `starter-assets/` into a live stack without a new design pass
- Automatic execution of prototype **archive** or **delete** (operator-driven; see `scripts/stage_archive_plan.sh`)

## Legacy workspace cleanup

After **you** confirm an off-host backup of `c:\Dev` (or equivalent), review printed commands from:

```bash
bash scripts/inventory_workspace.sh
bash scripts/stage_archive_plan.sh
```

Execute any `mkdir`/`mv` **manually** in Git Bash—never run `stage_delete_plan.sh` output until archives are verified.

## Conventions

- `.env` is gitignored; only `.env.example` is committed.
- Treat `starter-assets/reference-only/` as read-only inspiration.
