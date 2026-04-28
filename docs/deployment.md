# Phase 1 deployment (local Docker)

## Purpose

Run **Postgres + Metabase + n8n** on the workstation or a VM with **loopback-only** web ports. No TLS, no nginx, no public DNS—see `docs/architecture.md` for scope.

## Prerequisites

- Docker Engine and **Docker Compose v2** (`docker compose version`).
- **Git Bash** or **WSL** for `scripts/*.sh` (optional for compose itself).
- Disk space for named volumes (Postgres + n8n local data).

## First-time setup

1. From the repo root:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env`: set strong `POSTGRES_PASSWORD`, and set `MB_DB_PASS` / `DB_POSTGRESDB_PASSWORD` to match (or align with your chosen roles).

3. Start the stack:

   ```bash
   docker compose up -d
   ```

4. Wait for Metabase first-time boot (can take **1–3 minutes**). Then open:

   - Metabase: `http://127.0.0.1:8082/`
   - n8n: `http://127.0.0.1:8083/`

## Daily operations

| Task | Command |
|------|---------|
| View logs (follow) | `docker compose logs -f` |
| One service | `docker compose logs -f metabase` |
| Stop stack | `docker compose down` |
| Stop and remove containers (keeps volumes) | `docker compose down` |
| Recreate after `.env` change | `docker compose up -d --force-recreate` |

## Smoke checks

Requires `.env` present and stack running:

```bash
bash scripts/smoke.sh
```

Expect `PASS` lines for `docker compose config`, Metabase, and n8n HTTP.

## Reset data (destructive)

**Warning:** removes databases and n8n local files.

```bash
docker compose down
docker volume rm bratek-phase1-postgres-data bratek-phase1-n8n-data
docker compose up -d
```

You will need to complete **Metabase** and **n8n** first-run setup again.

## Postgres host access

Postgres is **not** published on the host. To run `psql` for debugging:

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d postgres
```

(use the username from `.env`)

## What this document excludes

- Archive / delete of old prototype trees (see `scripts/stage_archive_plan.sh` — **manual only**).
- Production TLS, reverse proxy, SSO.
- Backups of volumes (add a separate backup policy before relying on this data).
