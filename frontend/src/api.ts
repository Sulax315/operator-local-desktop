export type DesktopHealth = {
  status: string;
  backend_available: boolean;
  build_label: string;
  app_data_initialized: boolean;
  app_data_path: string;
  runtime_root: string;
  runs_root: string;
  project_library_accessible: boolean;
  project_library_path: string;
  indexed_workbooks: number;
};

export type WorkspaceStatus = {
  resolvable: boolean;
  workspace_root: string;
  project_index?: {
    indexed_workbooks?: number;
    live_workbook_count?: number;
    needs_scan?: boolean;
  };
};

export const BACKEND_URL =
  import.meta.env.VITE_OPERATOR_BACKEND_URL || "http://127.0.0.1:8092";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${BACKEND_URL}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getDesktopHealth(): Promise<DesktopHealth> {
  return getJson<DesktopHealth>("/api/desktop/health");
}

export function getWorkspaceStatus(): Promise<WorkspaceStatus> {
  return getJson<WorkspaceStatus>("/api/local/workspace");
}
