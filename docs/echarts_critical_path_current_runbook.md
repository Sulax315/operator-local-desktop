# ECharts — Critical tasks timeline (current snapshot)

## What this is (semantic contract)

This artifact is **not** a validated **CPM critical path** or **driver chain**.

- **Data:** `v_operator_critical_path_current` — incomplete tasks on the **current** snapshot that carry the schedule import’s **critical** flag, with `finish_date` present.
- **Order:** `strip_sequence` in SQL = **finish date, then start, then `task_id`** — **presentation only** for the chart strip.
- **Not included:** Pathfinding, predecessor/successor interpretation, or recomputing float logic in the API or browser.

For predecessor/successor **text**, use Metabase or query Postgres directly; the ECharts UI does **not** parse those fields.

## Prerequisites

- Postgres with `schedule_tasks` loaded.
- Deploy views: `sql/04_signals.sql` (creates `v_operator_critical_path_current`).

## Standard startup (recommended)

When Postgres is **already** running (avoids Compose trying to recreate the DB container on some hosts):

```bash
cd /srv/operator-stack-clean
docker compose build operator_echarts
docker compose up -d operator_echarts --no-deps
```

## Runtime checks

**Container naming:** Compose uses `container_name: bratek-phase1-operator-echarts`.

**Process bind:** The app listens on `**0.0.0.0:8090`** inside the container (`uvicorn` in `web/operator_echarts/Dockerfile`).

**Host port:** Compose maps `**0.0.0.0:8090:8090`** — port **8090** on all host interfaces. Restrict with a host firewall if the VM is reachable from untrusted networks.

```bash
docker ps --filter name=operator-echarts --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
docker logs bratek-phase1-operator-echarts --tail 40
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/api/health
```

## Access (choose one)

### On the VM itself

- Recently slipped: **[http://127.0.0.1:8090/](http://127.0.0.1:8090/)**
- Critical tasks: **[http://127.0.0.1:8090/critical-path](http://127.0.0.1:8090/critical-path)**

### From your laptop (SSH tunnel — safe default)

If the host only exposes **8090** on the VM’s loopback or you prefer not to expose the port publicly:

```bash
ssh -L 8090:127.0.0.1:8090 root@<vm-ip>
```

Then open **[http://127.0.0.1:8090/](http://127.0.0.1:8090/)** on the laptop.

### From the LAN / VM public IP (compose as shipped)

With `0.0.0.0:8090:8090`, open:

**http://****:8090/**

Use host firewall rules to limit sources if needed.

### Optional later (not in this repo’s Compose)

Reverse proxy + TLS (e.g. **echarts.bratek.io** → `operator_echarts:8090`) is an **infrastructure** step; root `docker-compose.yml` intentionally does not ship nginx (see `docs/architecture.md`).

## Verify API

```bash
curl -sS http://127.0.0.1:8090/api/operator/critical-path-current | head -c 2000
```

Expect `snapshot_context`, `rows` (ordered by `strip_sequence`), `row_cap` (default **100**).

## Verify view in Postgres

```bash
docker exec -i "$(docker ps -qf 'name=phase1-postgres')" psql -U "${POSTGRES_USER:-bratek_ops}" -d "${POSTGRES_DB:-postgres}" \
  -c "SELECT COUNT(*) FROM v_operator_critical_path_current;"
```

## Navigation

Both operator pages include a top **nav bar**: **Recently Slipped** | **Critical Tasks (Current Snapshot)** — no manual URL guessing required once you know the host/port.

## Future: true driver-path dataset (not implemented)

**Current limitation:** There is **no** canonical ordered **driver-path** relation in Postgres (no authoritative `path_sequence` from the scheduling tool in this stack).

**Required future input (one of):**

- `path_sequence` (or equivalent) exported from the scheduling engine **into** `schedule_tasks` or a dedicated table/view, **or**
- An **authoritative SQL view** that defines an ordered driver chain using only stored fields (still no pathfinding in Python/JS).

Normative truth-layer write-up: `**docs/driver_path_data_contract.md`** (feasibility **C** until import provides sequencing).

Until then, this chart remains **critical incomplete tasks on the current snapshot** only.

## Governance

Metabase remains the primary operator dashboard. Phase 4 rules: `**MASTER-PLAN-UPDATED-V5.txt`**.