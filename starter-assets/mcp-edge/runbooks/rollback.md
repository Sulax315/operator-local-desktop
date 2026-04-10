# Runbook: rollback MCP gateway

## Goal

Restore previous behavior if a gateway release fails (bad TLS, bad nginx config, broken image).

## Fast exit (stop gateway only)

On the VM, from `mcp_gateway/`:

```bash
docker compose down
```

This **does not** stop ScheduleLab, Control Tower, ProfitIntel, or WorkOS — it only stops this Compose project (`COMPOSE_PROJECT_NAME=mcp_gateway` by default).

## Revert to previous images

If you tagged images before deploy:

```bash
# example — replace with your registry/tag workflow
docker compose pull
docker compose up -d
```

If deploy used only local builds:

```bash
git checkout <known-good-commit>   # for infra repo / this directory
docker compose build --no-cache
docker compose up -d
```

## TLS failure

If nginx fails to start because of bad certs:

```bash
docker compose logs nginx
ls -la tls/   # or Let's Encrypt path
./ops/scripts/bootstrap_tls.sh   # lab only
# prod: re-run certbot fix / restore PEM backup
```

## Partial failure

- **sample_mcp unhealthy:** `docker compose logs sample_mcp` — nginx will not mark edge healthy until upstreams pass healthchecks (Compose `depends_on: condition: service_healthy`).
- **auth_sidecar unhealthy:** verify `MCP_BEARER_TOKEN` is set identically for nginx? **Note:** token is **only** consumed by auth_sidecar; nginx forwards the header. Redeploy after `.env` change: `docker compose up -d --force-recreate`.

## DNS rollback

Point `mcp.bratek.io` away from the VM or remove record if you need to stop exposure immediately.
