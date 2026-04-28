# Metabase API publish runbook — Recently Slipped signal

**Governance status:** Part of **Phase 2 extension** (Metabase REST automation). Live-proven alongside the guarded wrapper (`operator_run_snapshot_cycle.py`). **Phase 4** adds projection-only ECharts (`web/operator_echarts/`, port **8090**) in parallel — Metabase is not replaced. Authoritative phases: **`MASTER-PLAN-UPDATED-V5.txt`**, **`MASTER-PLAN-UPDATED-V4.txt`**.

## Purpose

This runbook describes how to run `scripts/publish_recently_slipped_metabase.py`, a VM-local publisher that uses the **Metabase REST API** (not the browser, not serialization) to:

- Upsert three native SQL saved questions backed only by Postgres views (no business logic in Metabase).
- Attach those questions to an existing dashboard once, without duplicating cards on reruns.

Instance API behavior is defined by the OpenAPI document served by Metabase at:

- `{METABASE_BASE_URL}/api/docs` (Scalar UI)
- `{METABASE_BASE_URL}/api/docs/openapi.json` (machine-readable schema)

On this stack, loopback Metabase listens on `http://127.0.0.1:8082` (see `docker-compose.yml`).

## Prerequisites

- Python 3 with the `requests` library (`python3 -c "import requests"`). If missing: `pip install requests`.
- Network reachability from the VM to `METABASE_BASE_URL`.
- A Metabase **API key** or **username/password** for an account that can read/write collections, cards, and the target dashboard.
- The Postgres data source already added in Metabase (`METABASE_DATABASE_NAME` must match the name shown in Admin → Databases).
- Postgres views already deployed: `v_signal_recently_slipped_tasks`, `v_schedule_snapshot_pair_latest`.

## Environment variables

See `config/metabase_publish.env.example` for placeholders. Required variables:

| Variable | Description |
|----------|-------------|
| `METABASE_BASE_URL` | e.g. `http://127.0.0.1:8082` or `https://metabase.example.com` |
| `METABASE_VERIFY_TLS` | `true` or `false` (use `false` only for dev HTTPS with private CAs) |
| `METABASE_API_KEY` | **or** username/password below |
| `METABASE_USERNAME` / `METABASE_PASSWORD` | **or** API key above |
| `METABASE_DATABASE_NAME` | Postgres source name inside Metabase |
| `METABASE_COLLECTION_NAME` | Target collection (created under root if it does not exist) |
| `METABASE_DASHBOARD_ID` | Preferred: numeric dashboard id |
| `METABASE_DASHBOARD_NAME` | Fallback if `METABASE_DASHBOARD_ID` is empty |

Optional:

- `--env-file PATH` — load `KEY=value` lines into the environment before reading `os.environ`. Lines may optionally start with `export ` (same as a bash-sourcable file).

## Test authentication

**API key**

```bash
curl -sS -H "X-Api-Key: $METABASE_API_KEY" \
  "$METABASE_BASE_URL/api/user/current"
```

Expect JSON with your Metabase user, not `Unauthenticated`.

**Session**

```bash
curl -sS -X POST "$METABASE_BASE_URL/api/session" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$METABASE_USERNAME\",\"password\":\"$METABASE_PASSWORD\"}"
```

Expect `{"id":"<uuid>"}`. Use that token as header `X-Metabase-Session` on subsequent calls (the script does this automatically).

## Run the publisher

Dry run (GET-only classification; skips POST/PUT except login; if the target collection does not exist yet, the script exits with a note to run a real pass first):

```bash
python3 scripts/publish_recently_slipped_metabase.py --dry-run
```

Apply changes:

```bash
python3 scripts/publish_recently_slipped_metabase.py
```

## Verify in Metabase

1. Open the target dashboard by id or name.
2. Confirm tiles for:
   - **Snapshot Pair Header** (single-row table).
   - **Recently Slipped Tasks Count** (scalar).
   - **Recently Slipped Tasks** (table).
3. Open each saved question from the collection and run it; results should come from the views only.

## Rerun behavior

- Questions are matched by **exact name** inside the target collection. Existing cards are **updated in place** (same id).
- Duplicate cards with the same name are **archived** after the dashboard is rewired to the canonical (lowest id) card.
- Legacy snapshot helper card **`v_snapshot_pair`** in the same collection is **renamed and repointed** to **Snapshot Pair Header** when the new name does not yet exist.
- Dashboard tiles are matched by **card id**; missing tiles are **added** in the first free grid slots near the top; existing placements are left unchanged.

## Common failure modes

| Symptom | Likely cause |
|---------|----------------|
| `Unauthenticated` / 401 | Missing or invalid API key or password |
| `No database named ...` | `METABASE_DATABASE_NAME` does not match Metabase UI |
| `No dashboard named ...` | Wrong `METABASE_DASHBOARD_NAME` or empty `METABASE_DASHBOARD_ID` |
| TLS errors on HTTPS | Set `METABASE_VERIFY_TLS=false` only if appropriate |
| 400 on dashboard PUT | Instance version expects extra fields; compare your PUT body to `openapi.json` for `PUT /api/dashboard/{id}` |
| SQL error in card | Views missing in Postgres or DB connection points at wrong database |

## Rollback

- **Remove dashboard tiles**: In Metabase, edit the dashboard and remove the added cards, or `GET` then `PUT` the dashboard with a filtered `dashcards` list (same OpenAPI schema).
- **Archive saved questions**: `PUT /api/card/{id}` with `"archived": true` (or use the Metabase UI Trash).
- **Restore old SQL**: Use Metabase revision history on the card if available, or re-run an older version control export you maintain separately.

Do not rely on Metabase **serialization** for git workflows unless your license includes it (Pro/Enterprise); this publisher uses only the REST API.
