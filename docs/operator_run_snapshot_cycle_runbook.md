# Operator run snapshot cycle — guarded execution runbook

## Purpose

`scripts/operator_run_snapshot_cycle.py` is the **first OpenClaw-ready execution target** for Bratek Operator Stack. It wraps an already-validated VM workflow into one repeatable command:

1. Optionally run the approved bash loader (`phase2_load_and_signals.sh`) without reimplementing its logic.
2. Run **read-only validation SQL** against PostgreSQL to confirm snapshot truth-layer assumptions.
3. Optionally delegate to `publish_recently_slipped_metabase.py` for Metabase API wiring.

This script **does not own schedule logic**. Snapshots, constraints, and signals remain authoritative in PostgreSQL and the checked SQL assets (`sql/01_schema.sql`, `sql/04_signals.sql`, etc.). The wrapper only orchestrates subprocesses and records auditable outcomes.

## Architectural boundary

| Owns schedule / signal semantics | Does **not** |
|----------------------------------|--------------|
| PostgreSQL tables, constraints, views | Metabase (presentation only) |
| `sql/*.sql` applied via loader | Python “second engine” for deltas or slips |
| Existing publisher’s embedded SQL strings (native questions pointing at views) | Browser automation |

OpenClaw or a future execution plane may invoke this script as a **deterministic, audited** step. It must not become a parallel truth layer: validation confirms Postgres state; it does not recompute business outcomes in Python.

## Why this exists

Phase 1–2 and Phase 2 extension established dual-snapshot coexistence, idempotent loads, and Metabase API automation. **Phase 3’s first OpenClaw-aligned execution target** (`operator_run_snapshot_cycle.py`) is **live-proven** (validate-only, publish dry-run, and validate+publish). This runbook documents that guarded entry point, which:

- Keeps operator steps linear and repeatable.
- Surfaces **PASS / FAIL** with per-check detail.
- Emits **timestamped JSON** under `runtime/operator_audit/` for governance and later automation.

**Next (governance):** expand the **execution layer** with additional audited commands—same architectural boundaries; no truth-logic migration, no ECharts/UI product drift unless explicitly scheduled.

## Prerequisites

- **Python 3** (stdlib + same deps as the publisher: `requests` when publishing).
- **Validation transport (pick one):**
  - **URI mode:** `psql` on the host and `--database-url` or `OPERATOR_DATABASE_URL` / `DATABASE_URL`.
  - **Docker mode:** `docker` on the host; the wrapper runs `docker exec <container> psql ...`. No host `psql` required for this path.
- For **load**: same Postgres container must be reachable from Docker as for validation; CSV path must exist; `--snapshot-date` and `--load-label` when load is enabled.
- For **publish**: Metabase env as in [metabase_api_publish_runbook.md](metabase_api_publish_runbook.md) and [config/metabase_publish.env.example](../config/metabase_publish.env.example); use `--metabase-env-file` or export variables before invocation. Env files may use either `KEY=value` or `export KEY=value` lines (the publisher strips `export ` when loading).

## Container naming and connection precedence

`docker-compose.yml` sets **`container_name: bratek-phase1-postgres`**. Some VMs still run an older Compose project-prefixed name such as **`9e60004df82e_bratek-phase1-postgres`** (only one such container should match).

**Precedence for validation transport**

1. If a database URL is available (**`--database-url` / `--db-url`** > **`OPERATOR_DATABASE_URL`** > **`DATABASE_URL`**), validation uses **host `psql` against that URI**. Docker container flags are **not** used for validation.
2. Otherwise validation uses **`docker exec`** against a resolved container name:
   - **`--db-container`** or **`--postgres-container`** (same flag, two spellings),
   - else **`OPERATOR_DB_CONTAINER`**,
   - else **auto-discover**: among running containers, use `bratek-phase1-postgres` if present, otherwise the **sole** name ending with `_bratek-phase1-postgres`,
   - else fall back to the literal name **`bratek-phase1-postgres`** (may fail if nothing is listening under that exact name).

The audit JSON includes a top-level **`connection_resolution`** object describing which branch ran (`validation_transport`, URL resolution note, container resolution note, `effective_postgres_container`).

## Modes of operation

| Mode | Flags | Steps |
|------|-------|-------|
| Validate only | `--skip-load` `--skip-publish` | preflight `SELECT 1` → truth-layer checks |
| Validate + publish | `--skip-load` | validate → publish |
| Load + validate + publish | `--snapshot-date`, `--load-label`, optional `--csv-path` | load → validate → publish |
| Publish dry-run | add `--publish-dry-run` | publish with publisher `--dry-run` |

## How to run

Working directory should be the **repository root** (the wrapper sets subprocess `cwd` there so the loader’s `sql/` paths resolve).

### Validate only (recommended smoke on the VM)

```bash
cd /srv/operator-stack-clean
python3 scripts/operator_run_snapshot_cycle.py --skip-load --skip-publish
```

With extra stderr progress:

```bash
python3 scripts/operator_run_snapshot_cycle.py --skip-load --skip-publish --verbose
```

### Validate + publish

```bash
cd /srv/operator-stack-clean
python3 scripts/operator_run_snapshot_cycle.py \
  --skip-load \
  --metabase-env-file config/metabase_publish.env
```

### Load + validate + publish

```bash
cd /srv/operator-stack-clean
python3 scripts/operator_run_snapshot_cycle.py \
  --snapshot-date 2026-04-09 \
  --load-label nightly_export_001 \
  --csv-path data/EXPORT_003-2026-04-09_UTF8.csv \
  --metabase-env-file config/metabase_publish.env
```

### Explicit Postgres container (disable auto-discover)

When multiple Compose projects could match, pin the name:

```bash
python3 scripts/operator_run_snapshot_cycle.py \
  --skip-load \
  --postgres-container 9e60004df82e_bratek-phase1-postgres \
  --metabase-env-file config/metabase_publish.env
```

Or via env (applies to both validation and load unless overridden):

```bash
export OPERATOR_DB_CONTAINER=9e60004df82e_bratek-phase1-postgres
python3 scripts/operator_run_snapshot_cycle.py --skip-load --skip-publish
```

### Host `psql` against a URL (no `docker exec` for validation)

```bash
python3 scripts/operator_run_snapshot_cycle.py \
  --skip-load \
  --database-url 'postgresql://USER:PASS@127.0.0.1:5432/postgres' \
  --metabase-env-file config/metabase_publish.env
```

### Publish dry-run path

```bash
python3 scripts/operator_run_snapshot_cycle.py \
  --skip-load \
  --publish-dry-run \
  --metabase-env-file config/metabase_publish.env
```

The publisher still performs reads and auth per [metabase_api_publish_runbook.md](metabase_api_publish_runbook.md); mutating API calls are skipped.

## Expected outputs

- **Stdout**: `OVERALL_STATUS: PASS|FAIL`, then `Audit written: <path>`.
- **Stderr (on FAIL):** `PRIMARY_FAILURE: scope=... category=...` when a classified failure event exists (see audit `failure_events`).
- **Exit code**: `0` if overall **PASS**, non-zero if **FAIL** (validation, load, publish, or audit write error).
- **stderr**: Optional progress lines when `--verbose` is set.

## Audit JSON

Every run writes one file:

- **Directory**: `runtime/operator_audit/` (override with `--audit-dir`).
- **Filename**: `operator_run_snapshot_cycle_<UTC-timestamp>.json` (colons in time are replaced for portability).

Top-level shape (additive fields for hardening):

- `run_started_at`, `run_finished_at` — ISO 8601 UTC.
- `overall_status` — `PASS` or `FAIL`.
- `execution_mode` — e.g. `validate`, `validate+publish`, `load+validate+publish`.
- `connection_resolution` — how validation connected (URI vs Docker, precedence notes, effective container name if Docker).
- `failure_events` — ordered list of `{scope, category, message, detail}` for operator triage (empty on clean PASS).
- `inputs` — includes `argv`, snapshot/load flags, paths, `effective_db_container`, etc.
- `steps.load` — invoked/skipped, subprocess argv, exit code, stdout/stderr tails, errors.
- `steps.validation` — `preflight` (`SELECT 1`), `PASS`/`FAIL`/`ERROR`, per-check records, `connection` echo.
- `steps.publish` — same pattern as load for the publisher subprocess.
- `summary` — short status mirror.
- `errors` — human-readable strings (may mirror `failure_events`).

## Failure modes

| Console / audit signal | Meaning |
|------------------------|---------|
| `PRIMARY_FAILURE: scope=validation_preflight category=missing_docker_container` | `docker exec` target name not running (see stderr in `preflight`) |
| `category=missing_docker` | `docker` binary not on `PATH` |
| `category=missing_psql` | URI mode requested but `psql` not installed |
| `category=db_connection_failure` | Postgres rejected connection or network refused (URI or exec) |
| `scope=validation_sql` + truth-layer IDs | SQL ran but truth assumptions failed (**FAIL**) or client/server error (**ERROR**); check `failure_category` in check `detail` |
| `scope=load` | Bash loader subprocess failed |
| `scope=publish` | Metabase publisher subprocess failed |
| `scope=wrapper` | Argument/configuration error or unexpected Python exception |
| `cannot write audit log` | Filesystem permissions on `--audit-dir` |

## PASS / FAIL interpretation

- **PASS**: Every executed step succeeded; preflight and all validation checks report **PASS**; publish succeeded if not skipped.
- **FAIL**: Any load failure, preflight failure, any validation **FAIL** or **ERROR**, publish failure, or configuration error that prevents a safe run.

Skipped steps do not by themselves cause FAIL (e.g. `--skip-publish` with successful validation yields overall **PASS**).

## OpenClaw alignment

Treat this CLI as a stable contract:

- Fixed flags and predictable exit codes.
- Structured JSON side effect for every invocation.
- No hidden UI steps.
- No duplicated schedule semantics in the wrapper.

Later automation should call this script verbatim and consume the audit JSON plus process exit code.

## Related documents

- Loader pipeline: `scripts/phase2_load_and_signals.sh`
- Metabase publisher: `scripts/publish_recently_slipped_metabase.py`, [metabase_api_publish_runbook.md](metabase_api_publish_runbook.md)
- Schema and views: `sql/01_schema.sql`, `sql/04_signals.sql`
