# MCP edge (starter pattern)

## Source

Extracted from `c:\Dev\mcp_gateway\` (prototype workspace).

## Why extracted

Demonstrates a **containerized TLS nginx** front, **bearer `auth_request`** via a tiny Python sidecar, **rate limiting**, path-based routing to internal MCP HTTP services, and **Compose health-gated startup**.

## Reuse

- Copy nginx layout and auth sidecar into a new gateway repo.
- Use runbooks as checklists for TLS issuance and verification.

## Confidence

**High** for nginx + sidecar + operational docs. **Compose file is incomplete in this pack**: build contexts for `sample_mcp`, `schedulelab_mcp`, `controltower_mcp`, etc. point at directories **not** shipped here. Either prune the compose to only `nginx` + `auth_sidecar` or supply your own downstream images.

## Contents

| Item | Role |
|------|------|
| `docker-compose.yml` | Full-stack reference (needs sibling Dockerfiles or edits) |
| `nginx/` | Main config + `conf.d` vhost |
| `.env.example` | Secrets and mount paths |
| `runbooks/` | deploy / verification / rollback |
| `auth_sidecar/` | Self-contained Dockerfile + FastAPI verifier |
