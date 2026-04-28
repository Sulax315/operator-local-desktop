# Asta Schedule Upload Runbook

## Purpose

`web/asta_upload` is a thin intake shell in front of the existing authoritative pipeline:

- Upload Asta CSV from browser
- Validate against the current import contract
- Execute `scripts/phase2_load_and_signals.sh`
- Show execution status + logs
- Link to Metabase

It does **not** replace SQL truth-layer logic, ingestion semantics, or Metabase.

## Integration Boundary

- **Truth layer:** PostgreSQL + existing SQL files
- **Loader:** `scripts/phase2_load_and_signals.sh`
- **Operator read surface:** Metabase (`https://metabase.bratek.io`)
- **Upload shell:** `asta_upload` FastAPI service on `127.0.0.1:8091`

## Upload Contract Validation

The upload service validates CSV before execution:

1. `.csv` extension
2. Non-empty file
3. Header row exists
4. Header matches current import contract used by loader:
   - `Task ID, Task name, Unique task ID, Duration, Duration remaining, Start, Finish, Early start, Early finish, Late start, Late finish, Total float, Free float, Critical, Predecessors, Successors, Critical path drag, Phase Exec, Control Account, Area Zone, Level, CSI, System, Percent complete, Original start, Original finish`
5. At least one non-empty data row

## Storage Paths

All upload artifacts are stored under:

- `runtime/upload_intake/uploads/` (uploaded CSVs)
- `runtime/upload_intake/runs/<run-id>/stdout.log`
- `runtime/upload_intake/runs/<run-id>/stderr.log`
- `runtime/upload_intake/runs/<run-id>/metadata.json`
- `runtime/upload_intake/latest_run.json`
- `runtime/upload_intake/execution.lock`

## Execution Locking

- Single-run lock uses `fcntl` lock file (`execution.lock`).
- If a run is active, new submissions are rejected with a clear message.

## Security Guardrails

- Service binds to loopback only (`127.0.0.1:8091`) in compose.
- Upload path is fixed and controlled; no user path input is used.
- Filenames are sanitized.
- File size cap enforced (`ASTA_UPLOAD_MAX_UPLOAD_BYTES`).
- Script execution is fixed to configured loader path; no arbitrary command input.
- Runtime output redacts common password env patterns before rendering.
- Recommended publication pattern: dedicated hostname + Cloudflare Access.

## Deploy / Start

From repo root:

```bash
docker compose build asta_upload
docker compose up -d asta_upload --no-deps
docker compose logs -f asta_upload
```

Health check:

```bash
curl -sS http://127.0.0.1:8091/health
```

## Publish via Zero Trust

Recommended dedicated hostname: `upload.bratek.io`.

Use existing helper:

```bash
sudo python3 tools/zt_app.py create upload.bratek.io 8091
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d upload.bratek.io
sudo python3 tools/zt_app.py validate upload.bratek.io
```

Then apply Cloudflare tunnel/DNS/Access policy per:

- `docs/zero-trust-app-deployment-protocol.md`
- `tools/zt_app.py print-cloudflare upload.bratek.io`

## Access URL

- Local VM: `http://127.0.0.1:8091`
- Published internal hostname (recommended): `https://upload.bratek.io`

## Operator Workflow

1. Open upload page.
2. Drag/drop Asta CSV.
3. Enter `snapshot_date` (required by loader contract).
4. Optionally set load label.
5. Submit and wait for completion.
6. Review checklist + stdout/stderr.
7. Click **Open Metabase**.

## Troubleshooting

- **"Another upload execution is currently running"**
  - Wait for active run to complete; check `runtime/upload_intake/latest_run.json`.
- **Header validation fail**
  - Export a standard Asta CSV with expected header contract/order.
- **Pipeline fails**
  - Review `stderr` in UI and `runtime/upload_intake/runs/<run-id>/stderr.log`.
  - Confirm `bratek-phase1-postgres` container exists and is healthy.
- **Load script not found**
  - Verify `ASTA_UPLOAD_LOAD_SCRIPT` and repo mount in compose.
- **Dry-run mode accidentally left on**
  - Set `ASTA_UPLOAD_EXECUTION_MODE=live` and restart `asta_upload`.

## Optional Safe Test Mode

Set in `.env`:

```bash
ASTA_UPLOAD_EXECUTION_MODE=dry_run
```

In dry-run mode, uploads validate and execution metadata/logs are produced, but the loader is not invoked.
