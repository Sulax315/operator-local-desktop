# Operator Local UI

**Status:** the browser surface is an **operator assistant workspace** in progress. Earlier single-form layouts were a **temporary harness** to drive the engine; the target UX is a desktop-class **workspace** (run rail, center intake + tabbed results, run-aware assistant, evidence), not a generic upload + giant card. Product definition: `build_control/operator_local/21_PRODUCT_DEFINITION_OPERATOR_LOCAL.md`.

## Purpose

Primary user flow:

1. Open page
2. Drag/drop files
3. Execute workflow
4. Review run-aware assistant narrative, financial/extraction context, and evidence (artifacts as secondary)

The app keeps the existing engine intact and delegates execution to:

- `scripts/init_operator_run.py`
- `scripts/run_workflow.py`
- `scripts/validate_operator_run.py`

## Runtime model (this host)

There are **two supported modes**. Only one may listen on **port 8092** at a time.

| Mode | Ownership | uvicorn | Bind | Use when |
|------|-----------|---------|------|----------|
| **Stable** | `operator-local-ui.service` (systemd) | No `--reload` | `127.0.0.1:8092` | Normal long-lived service; tunnel and local curl use loopback. |
| **Dev** | Manual (`scripts/run_operator_local.sh`) | `--reload` | `127.0.0.1:8092` | Active code edits; auto-reload through the project venv. |

**Authoritative for day-to-day uptime on this host:** systemd **`operator-local-ui.service`**. The run script is **dev/reload only**; stop the service before using it so nothing else holds 8092.

**Python environment:** on this host, **`.venv-operator-ui`** at the repo root is required (see `operator-local-ui.service` `ExecStart`). The dev script calls uvicorn through `/srv/operator-stack-clean/.venv-operator-ui/bin/uvicorn`.

**URLs**

- **Local (loopback):** `http://127.0.0.1:8092` (and `http://localhost:8092`)
- **LAN:** not exposed by the standard dev or stable commands. Both bind to **`127.0.0.1`** so the UI is local/tunnel-only.
- **Tunnel:** `https://operator-local.bratek.io` — served by **`cloudflared-operator-local-ui.service`**, which reads `/etc/cloudflared/operator-local-ui.yml` and forwards to **`http://127.0.0.1:8092`**. The origin must be up (stable or dev uvicorn) or the tunnel returns errors.

Do not run **systemd `operator-local-ui` and `./scripts/run_operator_local.sh` at the same time**; the second listener will fail with an address-in-use error or fight for the port.

### Running from VM and accessing from laptop

When the Operator Local UI runs on the VM, `127.0.0.1` means "this same machine." A browser on your laptop that opens `http://127.0.0.1:8092` is looking at the laptop, not the VM, so it will fail unless the browser itself is running on the VM.

Use the VM IP address or the configured Cloudflare hostname instead:

```bash
./scripts/operator_ui_launch.sh
./scripts/operator_ui_verify.sh
```

Browser URL from your laptop:

```text
http://<VM_IP>:8092/?owbDebug=1
```

Or, when the Cloudflare tunnel is configured:

```text
https://operator.bratek.io/?owbDebug=1
```

### Switching modes (exact operator commands)

**Dev mode**

```bash
sudo systemctl stop operator-local-ui.service
# If something else still holds 8092:
# sudo ss -tlnp | grep 8092
# sudo kill <pid>   # only if appropriate
cd /srv/operator-stack-clean && ./scripts/run_operator_local.sh
```

**Stable mode**

```bash
# Stop manual uvicorn (terminal running the script, or kill the listener on 8092)
sudo systemctl daemon-reload
sudo systemctl start operator-local-ui.service
sudo systemctl status operator-local-ui.service --no-pager
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8092/
sudo systemctl status cloudflared-operator-local-ui.service --no-pager
```

After a unit-file edit, **`daemon-reload`** is required before **`start`**. If `systemctl status` warns that the unit changed on disk, reload first.

## Run locally

**Standard port is 8092.** Use the same URL the UI loads from (`http://127.0.0.1:8092` or `http://localhost:8092`) so relative `/api/...` and `/runs/...` calls succeed. If you use uvicorn’s default **8000** or another port (e.g. **9988**), the page may open but fetches will fail with “Failed to fetch” when the tab points at a different origin.

**Dev quick start** (from repo root, after venv + `pip install -r web/operator_local_ui/requirements.txt`). The script stops any process on port 8092 before launching uvicorn from `.venv-operator-ui`:

```bash
./scripts/run_operator_local.sh
```

Quick verification:

```bash
curl -s http://127.0.0.1:8092 | head -20
```

**Manual dev** (equivalent to the script):

```bash
cd /srv/operator-stack-clean
.venv-operator-ui/bin/pip install -r web/operator_local_ui/requirements.txt
.venv-operator-ui/bin/uvicorn web.operator_local_ui.app:app --host 127.0.0.1 --port 8092 --reload
```

**Stable mode** is started by systemd (no `--reload`, bind `127.0.0.1:8092`); see **Runtime model** above and the exact commands in host runbooks.

Open locally: [http://localhost:8092](http://localhost:8092) or [http://127.0.0.1:8092](http://127.0.0.1:8092)

### If the page loads but **Run analysis** shows `Failed to fetch`

That message means the **fetch** to `/runs`, `/runs/.../files`, or `/runs/.../execute` did not complete (not an application JSON error).

1. **Browser DevTools → Network** — find the red request; note URL, status, and “(failed)” vs `4xx`/`5xx`.
2. **Server log** — look for a Python traceback or a killed worker while uploading or executing.
3. **Large workbooks** — `execute` can take a while (extract + workflow + validate). A reverse proxy in front of uvicorn may need higher **`proxy_read_timeout`** / **`send_timeout`** or the connection is cut → browser shows `Failed to fetch`.
4. **Bind address** — if you open the UI via a **VM public IP**, start uvicorn with **`--host 0.0.0.0`** so it listens on all interfaces (default `127.0.0.1` only accepts local connections on the VM itself).
5. **CORS** — the app enables permissive CORS for local tooling; restart uvicorn after updating. Override with `OPERATOR_UI_CORS_ORIGINS` (comma-separated) if needed.

## API surface

- `GET /api/history` — recent run log (JSON; newest first)
- `POST /runs`
- `POST /runs/{id}/files`
- `POST /runs/{id}/execute` — returns `structured_output`, `assistant_view`, `financial_intake_artifacts` when applicable
- `GET /runs/{id}`
- `GET /runs/{id}/artifacts`
- `GET /runs/{id}/artifacts/{artifact_path}`

## Notes

- For financial compare, Excel inputs can produce **structured JSON snapshots** with **extraction confidence** metadata; markdown inputs still use diff heuristics.
- The CLI remains available as internal/admin fallback.
