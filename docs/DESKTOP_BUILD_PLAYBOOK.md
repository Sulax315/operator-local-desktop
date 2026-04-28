# Operator Local Desktop Build Playbook

## Architecture

Operator Local Desktop packages the existing Operator Workbench as a local desktop app without changing financial extraction logic, workbook interpretation, formulas, analysis rules, or API contracts.

- Frontend: React + Vite in `frontend/`.
- Backend: existing `web/operator_local_ui` FastAPI app, wrapped by `backend/app/main.py`.
- Desktop shell: Tauri in `src-tauri/`.
- Backend runtime: PyInstaller onefile sidecar named `backend_app`.
- Storage: user-space app-data folders, including SQLite state and run files.
- Installer: Tauri NSIS installer configured for current-user install, no admin rights.
- CI/CD: GitHub Actions Windows runner in `Windows Tauri Build`.

The existing workbench UI remains served by the local FastAPI backend. The React desktop shell performs startup health checks and embeds the local workbench from `http://127.0.0.1:8092/`.

## Runtime Storage

The desktop sidecar initializes these folders outside the install directory:

- Windows: `%LOCALAPPDATA%\OperatorLocal`
- Linux fallback: `$XDG_DATA_HOME/OperatorLocal` or `~/.local/share/OperatorLocal`

Under that root:

- `runtime/operator_ui/` stores session state, `run_history.json`, and `state/workspace_index.db`.
- `runs/` stores generated run artifacts.
- `project_library/` is the default local project library.

## Default Workspace Rule

On Windows, the desktop sidecar resolves the default Operator Local workspace in this order:

1. If `C:\Dev\Operator_Data` exists, use it.
2. Else, if `%OneDrive%\000 - 2 - COST MANAGEMENT\Operator_Data` exists, use it.
3. Else, if `%OneDriveCommercial%\000 - 2 - COST MANAGEMENT\Operator_Data` exists, use it.
4. Else, fall back to `%LOCALAPPDATA%\OperatorLocal\project_library`.

The app does not hard-fail when `C:\Dev\Operator_Data` or the OneDrive paths are unavailable. Runtime state and run artifacts still remain under the app-data root.

The active workspace path is reported by `/api/desktop/health` as `active_workspace_path` and by `/api/local/workspace` as `workspace_root`. Desktop health also reports `workspace_resolution_source`, `attempted_workspace_paths`, and `resolution_reason` for troubleshooting.

## Local Dev Instructions

From the repo root:

```bash
python -m venv .venv-desktop
. .venv-desktop/bin/activate
python -m pip install -r backend/requirements.txt
python -m backend.app.main --host 127.0.0.1 --port 8092
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:1420`. The backend health endpoint is `http://127.0.0.1:8092/api/desktop/health`.

## VM Dev Instructions

Use the same commands as local dev, but keep both services bound to loopback:

```bash
python -m backend.app.main --host 127.0.0.1 --port 8092
cd frontend && npm run dev
```

If you need browser access from a host machine, use SSH port forwarding rather than binding the backend to `0.0.0.0`.

## CI Build Instructions

The workflow is `.github/workflows/windows-tauri-build.yml` and is named `Windows Tauri Build`.

To run it manually:

1. Open the repository in GitHub.
2. Go to **Actions**.
3. Select **Windows Tauri Build**.
4. Choose **Run workflow**.
5. Download the uploaded artifact named `operator-local-windows-nsis` after the job completes.

It performs:

1. Checkout.
2. Setup Node.
3. `npm ci` from `frontend/`.
4. Build Vite frontend.
5. Setup Python.
6. Install backend dependencies.
7. Run PyInstaller against `backend/app/main.py`.
8. Move the sidecar to `src-tauri/binaries/backend_app-x86_64-pc-windows-msvc.exe`.
9. Setup Rust.
10. Build Tauri for Windows.
11. Produce an NSIS installer.
12. Upload installer artifacts.

The workflow prints diagnostics for checkout layout, `frontend/dist`, PyInstaller `dist`, `src-tauri/binaries`, and `src-tauri/target/release/bundle` so packaging failures identify the missing stage.

## Installer Artifact Location

GitHub uploads the artifact bundle as `operator-local-windows-nsis`.

Expected files come from:

```text
src-tauri/target/release/bundle/nsis/*.exe
src-tauri/target/release/bundle/nsis/*.nsis.zip
```

The sidecar expected by Tauri on Windows is:

```text
src-tauri/binaries/backend_app-x86_64-pc-windows-msvc.exe
```

Expected installer naming follows Tauri defaults, typically similar to:

```text
Operator Local_0.1.0_x64-setup.exe
```

## No-Admin Install Notes

The Tauri bundle is configured for NSIS `currentUser` install mode. Do not switch this build to MSI for the desktop target unless admin rights are explicitly acceptable.

## Validation Checklist

- `web/operator_local_ui` financial extraction modules are unchanged except packaging execution glue.
- Existing tests still pass.
- Backend binds only to `127.0.0.1`.
- `/api/desktop/health` returns `status: ok`.
- App-data folders are created outside the install directory.
- `src-tauri/binaries/backend_app-x86_64-pc-windows-msvc.exe` exists before Tauri build.
- Tauri produces an NSIS `.exe` installer.
- GitHub artifact `operator-local-windows-nsis` is uploaded.

## Troubleshooting

### Missing `package.json`

Run frontend commands from `frontend/`, not the repo root:

```bash
cd frontend
npm ci
```

### Missing Sidecar Exe

Confirm the PyInstaller step produced `dist/backend_app.exe` and the workflow moved it to:

```text
src-tauri/binaries/backend_app-x86_64-pc-windows-msvc.exe
```

Tauri resolves sidecar names by target triple, so the Windows file must include `x86_64-pc-windows-msvc`.

The workflow's **Diagnose sidecar placement** step should show the file before `npm run tauri build`.

### PyInstaller Hidden Import Failure

If the sidecar starts in CI but exits immediately with a missing module, add the missing module to the PyInstaller command in `.github/workflows/windows-tauri-build.yml`.

The current build already includes hidden imports for:

```text
web.operator_local_ui.app
operator_envelope
init_operator_run
run_workflow
validate_operator_run
uvicorn.logging
uvicorn.loops.auto
uvicorn.protocols.http.auto
uvicorn.protocols.websockets.auto
uvicorn.lifespan.on
```

It also collects `operator_workflows`, `openpyxl`, and `jinja2` data.

### Missing Icon

The fallback icon is `src-tauri/icons/icon.ico`. If Tauri rejects it, regenerate a valid `.ico` and keep the same path.

### MSI Requiring Admin

This build targets NSIS, not MSI. Confirm `src-tauri/tauri.conf.json` has:

```json
"targets": ["nsis"]
```

and:

```json
"installMode": "currentUser"
```

### GitHub Artifact Not Uploaded

Check that the Tauri build wrote installer files under:

```text
src-tauri/target/release/bundle/nsis/
```

The upload step uses `if-no-files-found: error`, so a missing artifact should fail the workflow clearly.

If the installer exists in a different folder, update the upload path in `.github/workflows/windows-tauri-build.yml` to match the actual Tauri output from the **Diagnose Tauri bundle output** step.

### Backend Health Check Failure

Check that the sidecar is running on `127.0.0.1:8092` and that `/api/desktop/health` responds. The desktop shell retries backend startup for up to 30 seconds before showing a clear local failure message.

Common causes:

- Port `8092` is already in use.
- PyInstaller missed a hidden import.
- The sidecar was not copied into `src-tauri/binaries/`.
- App-data directory creation failed under `%LOCALAPPDATA%\OperatorLocal`.

### Local Port Conflict

The desktop port strategy is deterministic: `127.0.0.1:8092`. Stop any existing Operator Workbench service on that port before launching the desktop build.
