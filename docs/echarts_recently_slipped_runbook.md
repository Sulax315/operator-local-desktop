# ECharts — Recently Slipped Tasks (Phase 4)

## Purpose

Single operator page backed by **read-only** HTTP JSON from Postgres views:

- `v_signal_recently_slipped_tasks` — rowset (signal semantics remain in SQL only).
- `v_schedule_snapshot_pair_latest` — snapshot pair header for subtitle context.

No schedule logic is implemented in the FastAPI app or in the browser beyond presentation (axes, tooltips, category order follows API row order).

## Governance

Authoritative program state: `**MASTER-PLAN-UPDATED-V5.txt`**. Metabase remains the primary operator BI surface; this service is an additional **projection-only** channel.

## Prerequisites

- Stack running: Postgres healthy (other services optional for this page).
- Views deployed (same as Metabase path): run loader / `sql/04_signals.sql` if needed.
- Build the operator ECharts image once: `docker compose build operator_echarts`

## Run

```bash
cd /srv/operator-stack-clean
docker compose build operator_echarts
```

**Recommended when Postgres is already running** (avoids the Compose recreate issue below):

```bash
docker compose up -d operator_echarts --no-deps
```

Fresh stack (Postgres not yet up):

```bash
docker compose up -d
```

Open in a browser (same service; top **nav bar** switches views):

- **[http://127.0.0.1:8090/](http://127.0.0.1:8090/)** — Recently slipped tasks.
- **[http://127.0.0.1:8090/critical-path](http://127.0.0.1:8090/critical-path)** — Critical tasks (current snapshot) timeline; see `docs/echarts_critical_path_current_runbook.md`.

Remote VM: **http://****:8090/** when Compose binds `0.0.0.0:8090`, or use `ssh -L 8090:127.0.0.1:8090 root@<vm-ip>` (documented in the critical-tasks runbook).

## API ordering (presentation contract)

`GET /api/operator/recently-slipped-tasks` returns rows in this order only (no extra filters):

1. `slip_days` **DESC**
2. `task_id` **ASC** (deterministic tie-break; not signal logic)

Up to `**row_cap`** rows (currently **50**), enforced in the API SQL `LIMIT`.

## Non-empty validation (reversible fixture)

Use this when production slipped-task rows are absent but you need to prove the chart path (bars, tooltips, ordering) end-to-end.

1. **Apply** — inserts six `schedule_tasks` rows (three `task_id`s × two snapshot dates) aligned to `v_schedule_snapshot_pair_latest`, all with the same positive slip (`20` days) so **task_id ASC** order is observable:
  ```bash
   docker exec -i "$(docker ps -qf 'name=phase1-postgres')" psql -U "${POSTGRES_USER:-bratek_ops}" -d "${POSTGRES_DB:-postgres}" \
     -v ON_ERROR_STOP=1 -f - < scripts/sql/echarts_slip_validation_fixture_apply.sql
  ```
   If your Postgres container name differs, set it explicitly instead of the `docker ps` filter (e.g. `bratek-phase1-postgres` or a legacy prefixed name).
2. **Verify API** — expect three rows in API order `echarts_fixture_slip`, `fixture_tie_a`, `fixture_tie_z`:
  ```bash
   curl -sS http://127.0.0.1:8090/api/operator/recently-slipped-tasks | jq '.rows[].task_id'
  ```
3. **Verify UI** — reload **[http://127.0.0.1:8090/](http://127.0.0.1:8090/)** and confirm three horizontal bars, tooltips show full `task_name` / dates / `slip_days`, and bar order matches the API order (top bar = first row).
4. **Revert** (removes every row with `load_label = 'echarts_validation_fixture'`):
  ```bash
   docker exec -i "$(docker ps -qf 'name=phase1-postgres')" psql -U "${POSTGRES_USER:-bratek_ops}" -d "${POSTGRES_DB:-postgres}" \
     -v ON_ERROR_STOP=1 -f - < scripts/sql/echarts_slip_validation_fixture_revert.sql
  ```

**Real data path:** when schedule loads include two snapshots and tasks whose finish moves later, slipped rows appear without the fixture — compare Metabase “Recently Slipped Tasks” if published.

## Verify API

```bash
curl -sS http://127.0.0.1:8090/api/health
curl -sS http://127.0.0.1:8090/api/operator/recently-slipped-tasks | head -c 2000
```

Expect JSON with `snapshot_pair`, `rows` (possibly empty), and `row_cap`.

## Compose: Postgres container recreate / name conflict

**Symptom:** `docker compose up -d operator_echarts` (without `--no-deps`) fails with:

`The container name "/9e60004df82e_bratek-phase1-postgres" is already in use ...`

**Cause (observed with Compose file format 3.x + Compose 1.29.x):** bringing up `operator_echarts` triggers reconciliation of the `postgres` service and a **Recreate** path. Docker then tries to create a replacement container whose name is still held by the running Postgres instance, producing a **self-conflict** on the legacy auto-generated name (hash-prefixed + `bratek-phase1-postgres`).

**Primary remediation (safe, no data loss):** start the ECharts service without touching Postgres:

```bash
docker compose up -d operator_echarts --no-deps
```

**Optional long-term cleanup (brief DB outage, volume retained):** stop/remove only the Postgres *container* and recreate it so it matches `container_name: bratek-phase1-postgres` in `docker-compose.yml` (only if you accept a short outage and have verified backups / maintenance window). Data stays in the `postgres_data` volume.

**Manual attach (escape hatch):** build the image, discover the internal network (`docker network ls | grep phase1`), and `docker run` the ECharts image on that network with `--env-file .env` and `-p 127.0.0.1:8090:8090` (see prior runbook revisions for an example).

## Failure modes


| Symptom                | Check                                                                         |
| ---------------------- | ----------------------------------------------------------------------------- |
| 502 / `postgres_error` | Postgres not reachable from container; `PG`* env in compose                   |
| Empty chart            | Legitimate empty signal for current pair; compare Metabase “Recently Slipped” |
| Blank page             | Browser console; CDN blocked; ECharts script load                             |


## Stop

```bash
docker compose stop operator_echarts
```

