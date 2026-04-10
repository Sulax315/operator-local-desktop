# Control Tower Production Deployment Pack

This pack finishes the Linux droplet deployment for Control Tower using the repo's real architecture:

- one loopback-only FastAPI process on `127.0.0.1:8787`
- host nginx terminating TLS for `controltower.bratek.io`
- application-layer username/password auth on the public HTTPS hostname
- systemd supervising the always-on web process
- cron running the canonical daily and weekly operations
- persistent runtime state under a shared `.controltower_runtime/`

Routine releases now go through the authoritative workstation entrypoint documented in [`docs/PRODUCTION_RELEASE.md`](/C:/Dev/ControlTower/docs/PRODUCTION_RELEASE.md). The scripts in this folder remain the bootstrap/install substrate beneath that release lane.

## Canonical Paths

The provided examples assume:

- app root: `/srv/controltower/app`
- virtualenv: `/srv/controltower/venv`
- shared runtime root: `/srv/controltower/shared/.controltower_runtime`
- production config: `/etc/controltower/controltower.yaml`
- production env file: `/etc/controltower/controltower.env`

Adjust the example env and YAML files only where your droplet's existing ScheduleLab, ProfitIntel, Obsidian, or TLS certificate paths differ.

## Recommended Production Topology

- Backend process: `python /srv/controltower/app/run_controltower.py --config /etc/controltower/controltower.yaml serve --host 127.0.0.1 --port 8787`
- Public route: `https://controltower.bratek.io` proxied by nginx to `http://127.0.0.1:8787`
- Public entry point: `https://controltower.bratek.io/login`
- Runtime evidence: `/srv/controltower/shared/.controltower_runtime`
- Scheduler: cron for `daily` and `weekly`, because the repo already has stable scheduler-oriented wrapper scripts and file-backed operation logs

Systemd remains the recommended always-on supervisor for the web process.

## Install Files

1. Create the production env file:

```bash
sudo install -d /etc/controltower
sudo cp /srv/controltower/app/infra/deploy/controltower/controltower.production.env.example /etc/controltower/controltower.env
sudo editor /etc/controltower/controltower.env
```

2. Create the production YAML config:

```bash
sudo cp /srv/controltower/app/infra/deploy/controltower/controltower.production.yaml.example /etc/controltower/controltower.yaml
sudo editor /etc/controltower/controltower.yaml
```

3. Install or refresh the host assets:

```bash
sudo CONTROLTOWER_ENV_FILE=/etc/controltower/controltower.env bash /srv/controltower/app/infra/deploy/controltower/install_host.sh
```

4. Install the service, cron schedule, and nginx site:

```bash
sudo CONTROLTOWER_ENV_FILE=/etc/controltower/controltower.env bash /srv/controltower/app/infra/deploy/controltower/install_host.sh
```

5. Verify the live deployment:

```bash
CONTROLTOWER_ENV_FILE=/etc/controltower/controltower.env bash /srv/controltower/app/ops/linux/verify_controltower_production.sh --config /etc/controltower/controltower.yaml
```

Treat `verify_controltower_production.sh` as mandatory for release completion. The authoritative `deploy_update.sh` handoff consumes the checked-in remote script in this folder, writes the source trace into runtime state, confirms the auth gate is still intact, and stamps the release artifact with local `HEAD`, remote `origin/main`, deployed `GIT_COMMIT`, verification status, and verification timestamp.

## Installed Assets

- `templates/controltower-web.service.tpl`: systemd unit for the loopback FastAPI process
- `templates/controltower.cron.tpl`: cron schedule for the canonical daily and weekly runs
- `templates/controltower-nginx.conf.tpl`: nginx site for `controltower.bratek.io`
- `deploy_update.sh`: authoritative workstation release handoff
- `release_remote.sh`: internal remote deploy substrate invoked by `deploy_update.sh`
- `install_host.sh`: renders and installs systemd, cron, and nginx assets

## Manual Operator Commands

```bash
sudo systemctl restart controltower-web
sudo systemctl status controltower-web --no-pager
sudo journalctl -u controltower-web -n 100 --no-pager

source /etc/controltower/controltower.env
bash /srv/controltower/app/ops/linux/preflight_controltower.sh --config /etc/controltower/controltower.yaml
bash /srv/controltower/app/ops/linux/run_daily_controltower.sh --config /etc/controltower/controltower.yaml
bash /srv/controltower/app/ops/linux/run_weekly_controltower.sh --config /etc/controltower/controltower.yaml
bash /srv/controltower/app/ops/linux/smoke_controltower.sh --config /etc/controltower/controltower.yaml
bash /srv/controltower/app/ops/linux/diagnostics_snapshot_controltower.sh --config /etc/controltower/controltower.yaml
bash /srv/controltower/app/ops/linux/release_readiness_controltower.sh --config /etc/controltower/controltower.yaml --skip-pytest --skip-acceptance
```
