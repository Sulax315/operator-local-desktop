# Postgres Temp Pressure Monitoring Runbook

## Purpose

Provide a lightweight, non-invasive way to capture storage and Postgres evidence when refresh jobs intermittently fail with `No space left on device`, without changing product logic or infrastructure design.

## When to use this

- Before any heavy refresh/load run (routine pre-check).
- Immediately when a refresh fails with storage-like symptoms.
- After a failure to compare state deltas and decide whether to continue normal work or escalate with evidence.

## Evidence location

- Snapshot logs are written to `diagnostics/storage_pressure/`.
- Filenames are timestamped as `storage_snapshot_YYYYMMDD_HHMMSS.log`.

## MODE 1 - Routine pre-check before heavy refresh

Run:

```bash
bash scripts/capture_storage_pressure_snapshot.sh
```

Then quickly confirm:

- `df -h` shows healthy free space on host filesystems.
- `df -i` shows inode availability is not close to exhaustion.
- `docker system df` is not showing obvious image/container/volume bloat pressure.
- Postgres container is running and logs do not show immediate storage faults.
- Optional Postgres stats query (if successful) does not show unusual jump in `temp_bytes` versus recent baseline snapshots.

If all checks look normal, proceed with the refresh command as usual.

## MODE 2 - Failure capture (during/after refresh failure)

1) Preserve the failing command and exact error text from terminal output.

2) Immediately run:

```bash
bash scripts/capture_storage_pressure_snapshot.sh
```

3) If you have a known pre-run snapshot, diff them:

```bash
ls -1 diagnostics/storage_pressure/storage_snapshot_*.log
diff -u diagnostics/storage_pressure/storage_snapshot_PRE.log diagnostics/storage_pressure/storage_snapshot_POST.log
```

4) Compare:

- host disk and inode percentages (`df -h`, `df -i`)
- Docker footprint (`docker system df`, `/var/lib/docker` summary)
- Postgres container state/restarts/logs
- `pg_stat_database.temp_files` and `temp_bytes` (if query succeeded)

## Optional wrapper workflow

For one-command pre/post/failure capture around an existing refresh command:

```bash
bash scripts/run_refresh_with_storage_capture.sh -- <existing refresh command>
```

Example:

```bash
bash scripts/run_refresh_with_storage_capture.sh -- bash scripts/phase2_load_and_signals.sh
```

This wrapper does not alter the wrapped command; it only adds telemetry snapshots before/after, and on failure.

## Exact commands to run

### Before heavy refresh

```bash
bash scripts/capture_storage_pressure_snapshot.sh
<run your normal refresh command>
```

### During/after failure

```bash
bash scripts/capture_storage_pressure_snapshot.sh
```

### Optional Postgres container override (if detection is ambiguous)

```bash
POSTGRES_CONTAINER=<container_name> bash scripts/capture_storage_pressure_snapshot.sh
```

## Interpretation branches

### 1) Host disk full

Indicators:

- `df -h` shows one or more critical filesystems near 100%.
- Errors correlate with write activity timing.

Action:

- Treat as host storage pressure incident; free space per normal ops policy and re-run capture before/after remediation.

### 2) Inode exhaustion

Indicators:

- `df -i` shows very high inode usage (near 100%) even if byte capacity remains.

Action:

- Treat as inode pressure incident; identify and clean excessive small-file generators per ops policy, then re-capture.

### 3) Docker storage pressure

Indicators:

- `docker system df` reports unexpectedly large local Docker usage.
- `/var/lib/docker` summary increases sharply between snapshots.

Action:

- Treat as container storage pressure; perform approved, non-destructive cleanup review and capture again after action.

### 4) Postgres temp spill / container-local issue

Indicators:

- Host disk is generally healthy, but Postgres logs include temp-file or write failures.
- `pg_stat_database.temp_files` / `temp_bytes` spikes around failure window.
- Container status/restart counters or logs indicate local storage stress.

Action:

- Escalate with snapshots and failing command details for focused DB/container diagnostics in a separate investigation pass.

### 5) Transient condition not currently reproducible

Indicators:

- No strong pressure signal in disk/inode/docker/postgres metrics after recovery.

Action:

- Keep running with this capture workflow in place; collect snapshots again at next recurrence and compare trend history.

## Safe behavior and limitations

- Script is read-only and safe to run repeatedly.
- Missing commands are handled as warnings; capture continues.
- Postgres query is best-effort and bounded by timeout to avoid hangs.
- If DB query cannot run (auth/env/container mismatch), snapshot still remains useful from host/docker/log evidence.

## What to hand into a new ChatGPT investigation thread

Provide:

- failing refresh command (exact)
- exact error text (copy/paste)
- at least one pre-run and one failure/post-run snapshot file from `diagnostics/storage_pressure/`
- time window of incident and any operator actions taken
- note whether Postgres stats query succeeded or was skipped/failed
