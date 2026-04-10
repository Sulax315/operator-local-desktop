# Runbook: deploy MCP gateway (`mcp.bratek.io`)

## Preconditions

- Ubuntu VM with Docker Engine and Docker Compose plugin.
- DNS **A/AAAA record** for `mcp.bratek.io` pointing at the VM (document in verification if not yet live).
- Firewall: allow **443** (and **80** if using HTTP-01 challenge).

## One-time TLS (production)

Use Let’s Encrypt on the host (example with certbot standalone or webroot — align with your standard):

```bash
sudo certbot certonly --nginx -d mcp.bratek.io
# or: certonly --webroot -w /var/www/certbot -d mcp.bratek.io
```

Export PEM paths the stack expects inside nginx:

- **fullchain** → mounted as `/etc/nginx/tls/fullchain.pem`
- **privkey** → mounted as `/etc/nginx/tls/privkey.pem`

Example `.env` on the VM:

```bash
TLS_VOLUME_MOUNT=/etc/letsencrypt/live/mcp.bratek.io
```

Ensure the directory contains `fullchain.pem` and `privkey.pem` (or symlink them before mount names match).

## Lab / smoke TLS

From `mcp_gateway/`:

```bash
chmod +x ops/scripts/bootstrap_tls.sh
./ops/scripts/bootstrap_tls.sh
```

This creates `tls/fullchain.pem` and `tls/privkey.pem`.

## Configure secrets and data mounts

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # or: openssl rand -hex 32
# paste into MCP_BEARER_TOKEN=
# Also set MCP_PANEL_PASSWORD and MCP_PANEL_SESSION_SECRET for https://mcp.bratek.io/panel/
```

Confirm **`SCHEDULELAB_PUBLISHED_HOST_PATH`** points at the live ScheduleLab published tree on the VM (commonly `/app/schedulelab_data/published`) and **`CONTROLTOWER_RUNTIME_HOST_PATH`** at Control Tower runtime (commonly `/srv/controltower/shared/.controltower_runtime`). Wrong paths yield healthy containers but **degraded** `/health` JSON and tool `warnings`.

### VM template `.env` (`vm_rewrite_mcp_env.sh`)

`ops/scripts/vm_rewrite_mcp_env.sh` rewrites the gateway `.env` for the standard VM layout (loopback publish, host data paths). It **preserves** `MCP_BEARER_TOKEN`, **`MCP_PANEL_USER`**, **`MCP_PANEL_PASSWORD`**, and **`MCP_PANEL_SESSION_SECRET`** when present; if panel secrets are missing or still set to the `.env.example` placeholders, it **generates** new `MCP_PANEL_PASSWORD` and `MCP_PANEL_SESSION_SECRET` and prints a notice to stderr (save the password for operators).

## Deploy

```bash
cd /path/to/mcp_gateway
chmod +x ops/scripts/deploy_mcp_gateway.sh
./ops/scripts/deploy_mcp_gateway.sh
```

Or manually:

```bash
docker compose build --pull
docker compose up -d
docker compose ps
```

## Post-deploy inspection

```bash
docker compose logs -f --tail=100 nginx
docker compose logs -f --tail=100 sample_mcp
docker compose logs -f --tail=100 auth_sidecar
docker exec mcp_gateway_nginx nginx -t
docker compose ps
```

After deploy, from the VM (or any host that reaches the edge):

```bash
set -a && source .env && set +a
./ops/scripts/verify_mcp_gateway.sh
./ops/scripts/verify_mcp_panel.sh
```

## SNI / local curl

`server_name` is `mcp.bratek.io`. From another machine:

```bash
curl -sk --resolve mcp.bratek.io:443:YOUR_VM_IP https://mcp.bratek.io/health
```
