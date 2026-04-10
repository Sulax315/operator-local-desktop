# Runbook: verify MCP gateway acceptance

Run **`ops/scripts/verify_mcp_gateway.sh`** from `mcp_gateway/` on any host that can reach the edge URL (VM loopback or Internet with DNS + `MCP_BEARER_TOKEN` loaded from `.env`).

```bash
cd /path/to/mcp_gateway
set -a && source .env && set +a
export VERIFY_BASE_URL=https://mcp.bratek.io   # or https://127.0.0.1 with --resolve
chmod +x ops/scripts/verify_mcp_gateway.sh
./ops/scripts/verify_mcp_gateway.sh
```

## Operator control panel (session login)

After gateway verification, run **`ops/scripts/verify_mcp_panel.sh`** with the same `.env` (needs **`MCP_PANEL_PASSWORD`**; optional `MCP_PANEL_USER`).

```bash
cd /path/to/mcp_gateway
set -a && source .env && set +a
export MCP_VERIFY_BASE_URL=https://mcp.bratek.io   # or loopback + SNI if needed
chmod +x ops/scripts/verify_mcp_panel.sh
./ops/scripts/verify_mcp_panel.sh
```

This checks `/panel/`, `/panel/health`, login cookie flow, server and tool lists for all three backends, **`get_project_summary`** with `{"project_code":"SU_WAVERLY"}`, history, logout, and a heuristic that the HTML does not embed bearer-like material.

## Manual checklist (evidence)

1. **DNS:** `dig +short mcp.bratek.io` returns VM address (or document “pending” + use `--resolve`).
2. **TLS:** `curl -vI https://mcp.bratek.io/health` shows certificate chain valid in prod (or `-k` for lab).
3. **nginx routing:** `/health` returns JSON with `"gateway":"mcp_gateway"`.
4. **Sample health:** `GET /sample/health` returns `sample_mcp` JSON.
5. **Auth deny:** `curl -sk -o /dev/null -w "%{http_code}" -X POST https://mcp.bratek.io/sample/mcp` → **401** (or **403** before `error_page` mapping).
6. **Auth allow:** Same with `-H "Authorization: Bearer $MCP_BEARER_TOKEN"` → **not** 401/403 (MCP body may be protocol error for `{}` — acceptable).
7. **ScheduleLab / Control Tower health:** `GET /schedulelab/health` and `GET /controltower/health` return **200** JSON with `healthy` (may show `degraded` if host bind mounts are empty — document for ops).
8. **Production MCP paths:** Authenticated `POST` to `/schedulelab/mcp` and `/controltower/mcp` must **not** return 401 from nginx when the bearer is valid (protocol body may still error for `{}`).
9. **Structure:** New service adds Compose + nginx `location` only; existing Bratek stacks unchanged.

## Cursor (remote MCP)

In Cursor MCP settings, use remote Streamable HTTP URL and Bearer header:

| Server | URL |
|--------|-----|
| Sample | `https://mcp.bratek.io/sample/mcp` |
| ScheduleLab | `https://mcp.bratek.io/schedulelab/mcp` |
| Control Tower | `https://mcp.bratek.io/controltower/mcp` |

**Header:** `Authorization: Bearer <MCP_BEARER_TOKEN>`

Exact JSON shape depends on Cursor’s release; keys are typically `headers`/`env` in `mcp.json` — confirm against Cursor docs when enabling.

## Evidence bundle (save for audits)

- Redact token; keep: HTTP status codes, first 500 chars of `/health` responses, and `verify_mcp_gateway.sh` full stdout.
- Attach `docker compose ps` from the MCP gateway project.

See also **`docs/operator_discipline.md`** for provenance conventions and Obsidian logging.
