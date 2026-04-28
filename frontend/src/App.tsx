import { useEffect, useState } from "react";
import {
  BACKEND_URL,
  DesktopHealth,
  WorkspaceStatus,
  getDesktopHealth,
  getWorkspaceStatus,
} from "./api";

type LoadState =
  | { status: "loading"; attempt: number; message: string }
  | { status: "ready"; health: DesktopHealth; workspace: WorkspaceStatus }
  | { status: "error"; attempts: number; message: string };

const HEALTH_RETRY_ATTEMPTS = 30;
const HEALTH_RETRY_DELAY_MS = 1000;

function App() {
  const [state, setState] = useState<LoadState>({
    status: "loading",
    attempt: 1,
    message: "Starting local backend...",
  });

  useEffect(() => {
    let cancelled = false;
    let retryTimer: number | undefined;
    let refreshTimer: number | undefined;

    async function load(attempt: number) {
      if (!cancelled) {
        setState({
          status: "loading",
          attempt,
          message: `Waiting for local backend (${attempt}/${HEALTH_RETRY_ATTEMPTS})...`,
        });
      }

      try {
        const health = await getDesktopHealth();
        const workspace = await getWorkspaceStatus();
        if (cancelled) return;
        setState({ status: "ready", health, workspace });
        refreshTimer = window.setInterval(refresh, 5000);
      } catch (error) {
        if (cancelled) return;
        if (attempt < HEALTH_RETRY_ATTEMPTS) {
          retryTimer = window.setTimeout(() => load(attempt + 1), HEALTH_RETRY_DELAY_MS);
          return;
        }
        setState({
          status: "error",
          attempts: attempt,
          message: error instanceof Error ? error.message : "Backend health check failed",
        });
      }
    }

    async function refresh() {
      try {
        const [health, workspace] = await Promise.all([
          getDesktopHealth(),
          getWorkspaceStatus(),
        ]);
        if (!cancelled) setState({ status: "ready", health, workspace });
      } catch {
        if (!cancelled) {
          setState({
            status: "error",
            attempts: HEALTH_RETRY_ATTEMPTS,
            message: "Local backend stopped responding. Restart Operator Local.",
          });
        }
      }
    }

    load(1);
    return () => {
      cancelled = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      if (refreshTimer !== undefined) window.clearInterval(refreshTimer);
    };
  }, []);

  const workbenchUrl = `${BACKEND_URL}/`;

  return (
    <main className="desktop-shell">
      <header className="desktop-status">
        <div>
          <strong>Operator Local Desktop</strong>
          <span className="muted">Desktop delivery infrastructure</span>
        </div>
        {state.status === "ready" ? (
          <div className="status-grid" aria-label="Desktop health">
            <span>Backend: available</span>
            <span>App data: {state.health.app_data_initialized ? "ready" : "not ready"}</span>
            <span>
              Library: {state.health.project_library_accessible ? "accessible" : "missing"}
            </span>
            <span>Build: {state.health.build_label}</span>
          </div>
        ) : (
          <div className="status-grid">
            <span>{state.message}</span>
          </div>
        )}
      </header>

      {state.status === "ready" ? (
        <section className="workbench-frame" aria-label="Operator Workbench">
          <iframe title="Operator Workbench" src={workbenchUrl} />
        </section>
      ) : (
        <section className="startup-panel" aria-live="polite">
          <h1>Starting Operator Workbench</h1>
          <p>
            The desktop shell is waiting for the local FastAPI sidecar at{" "}
            <code>{BACKEND_URL}</code>.
          </p>
          {state.status === "loading" ? <p>{state.message}</p> : null}
          {state.status === "error" ? (
            <p className="error">
              Backend health check failed after {state.attempts} attempts: {state.message}
            </p>
          ) : null}
        </section>
      )}
    </main>
  );
}

export default App;
