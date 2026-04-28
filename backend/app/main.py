from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import uvicorn

APP_NAME = "OperatorLocal"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8092
BUILD_LABEL = os.environ.get("OPERATOR_DESKTOP_BUILD_LABEL", "desktop-dev")
WINDOWS_DEV_WORKSPACE = Path(r"C:\Dev\Operator_Data")
WINDOWS_OPERATOR_DATA_RELATIVE = Path(r"000 - 2 - COST MANAGEMENT\Operator_Data")


def _resource_root() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(str(bundled_root)).resolve()
    return Path(__file__).resolve().parents[2]


def _app_data_root() -> Path:
    override = os.environ.get("OPERATOR_DESKTOP_APP_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return (Path(local_app_data) / APP_NAME).resolve()

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return (Path(xdg_data_home) / APP_NAME).resolve()

    return (Path.home() / ".local" / "share" / APP_NAME).resolve()


def _default_workspace(app_data: Path) -> tuple[Path, str, list[str], str]:
    app_data_workspace = app_data / "project_library"
    attempted = [str(WINDOWS_DEV_WORKSPACE)]

    if os.name == "nt":
        if WINDOWS_DEV_WORKSPACE.exists():
            return (
                WINDOWS_DEV_WORKSPACE.resolve(),
                "windows_dev",
                attempted + [str(app_data_workspace)],
                r"C:\Dev\Operator_Data exists.",
            )

        for env_name in ("OneDrive", "OneDriveCommercial"):
            root = os.environ.get(env_name)
            if not root:
                continue
            candidate = Path(root) / WINDOWS_OPERATOR_DATA_RELATIVE
            attempted.append(str(candidate))
            if candidate.exists():
                return (
                    candidate.resolve(),
                    f"{env_name}_operator_data",
                    attempted + [str(app_data_workspace)],
                    f"{env_name} contains {WINDOWS_OPERATOR_DATA_RELATIVE}.",
                )

        return (
            app_data_workspace.resolve(),
            "app_data_fallback",
            attempted + [str(app_data_workspace)],
            "No preferred Windows workspace exists; using app-data fallback.",
        )

    return (
        app_data_workspace.resolve(),
        "app_data_fallback",
        attempted + [str(app_data_workspace)],
        "Non-Windows runtime; using app-data fallback.",
    )


def configure_desktop_environment() -> dict[str, Any]:
    resource_root = _resource_root()
    app_data = _app_data_root()
    runtime_root = app_data / "runtime" / "operator_ui"
    runs_root = app_data / "runs"
    project_library, workspace_source, attempted_paths, resolution_reason = _default_workspace(app_data)

    for path in (app_data, runtime_root, runs_root, project_library):
        path.mkdir(parents=True, exist_ok=True)

    for import_root in (resource_root, resource_root / "scripts"):
        if str(import_root) not in sys.path:
            sys.path.insert(0, str(import_root))

    os.environ["OPERATOR_UI_REPO_ROOT"] = str(resource_root)
    os.environ["OPERATOR_UI_RUNTIME_ROOT"] = str(runtime_root)
    os.environ["OPERATOR_UI_RUNS_ROOT"] = str(runs_root)
    os.environ["OPERATOR_UI_DEFAULT_LOCAL_WORKSPACE"] = str(project_library)
    os.environ["OPERATOR_UI_ALLOWED_WORKSPACES"] = os.pathsep.join(
        [str(project_library), str(Path.home()), str(runs_root)]
    )
    os.environ["OPERATOR_UI_CORS_ORIGINS"] = "*"
    os.environ["OPERATOR_UI_RUN_SCRIPTS_IN_PROCESS"] = "1"

    return {
        "resource_root": resource_root,
        "app_data": app_data,
        "runtime_root": runtime_root,
        "runs_root": runs_root,
        "project_library": project_library,
        "workspace_source": workspace_source,
        "attempted_workspace_paths": attempted_paths,
        "resolution_reason": resolution_reason,
    }


DESKTOP_PATHS = configure_desktop_environment()

from web.operator_local_ui import app as operator_app  # noqa: E402

app = operator_app.app


def _sync_desktop_workspace_config() -> None:
    operator_app._ensure_dirs()
    project_library = Path(str(DESKTOP_PATHS["project_library"]))
    operator_app._save_workspace_config(
        {
            "default_workspace_root": str(project_library),
            "allowed_workspace_roots": [
                str(project_library),
                str(Path.home()),
                str(DESKTOP_PATHS["runs_root"]),
            ],
        }
    )


_sync_desktop_workspace_config()


@app.get("/api/desktop/health")
def desktop_health() -> dict[str, Any]:
    _sync_desktop_workspace_config()
    cfg = operator_app._load_workspace_config()
    project_library = DESKTOP_PATHS["project_library"]
    workspace_root = str(cfg.get("default_workspace_root") or project_library)
    workspace_path = Path(workspace_root).expanduser()
    project_library_accessible = workspace_path.exists() and workspace_path.is_dir()
    indexed_workbooks = (
        operator_app._index_workbook_count_for_root(str(workspace_path.resolve()))
        if project_library_accessible
        else 0
    )
    return {
        "status": "ok",
        "backend_available": True,
        "build_label": BUILD_LABEL,
        "host": DEFAULT_HOST,
        "app_data_initialized": DESKTOP_PATHS["app_data"].exists(),
        "app_data_path": str(DESKTOP_PATHS["app_data"]),
        "runtime_root": str(DESKTOP_PATHS["runtime_root"]),
        "runs_root": str(DESKTOP_PATHS["runs_root"]),
        "active_workspace_path": str(workspace_path),
        "workspace_resolution_source": str(DESKTOP_PATHS["workspace_source"]),
        "attempted_workspace_paths": list(DESKTOP_PATHS["attempted_workspace_paths"]),
        "resolution_reason": str(DESKTOP_PATHS["resolution_reason"]),
        "project_library_accessible": project_library_accessible,
        "project_library_path": str(workspace_path),
        "indexed_workbooks": indexed_workbooks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Operator Local desktop backend sidecar")
    parser.add_argument("--host", default=os.environ.get("OPERATOR_DESKTOP_BACKEND_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("OPERATOR_DESKTOP_BACKEND_PORT", DEFAULT_PORT)))
    args = parser.parse_args()

    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Desktop backend must bind to localhost only.")

    os.chdir(DESKTOP_PATHS["resource_root"])
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
