# Operator ECharts — Production Runbook

This service (`web/operator_echarts`, Docker image `operator-stack-clean-operator_echarts`) exposes read-only schedule and financial projections on port **8090**.

## 1. Health endpoints

| Route | Purpose |
| --- | --- |
| `GET /api/health` | **Liveness** — process up; returns `version`, `environment`. Does not query Postgres. |
| `GET /api/health/ready` | **Readiness** — runs `SELECT 1` via app DB config; **503** if Postgres is unreachable. |

Orchestration: point Docker/Kubernetes health checks at **`/api/health/ready`**. Use **`/api/health`** only when you must not depend on the database (e.g. broken networking debugging).

## 2. Build and deploy

```bash
export OPERATOR_APP_VERSION="$(git rev-parse --short HEAD 2>/dev/null || echo dev)"
docker compose build operator_echarts
docker compose up -d operator_echarts
```

`OPERATOR_APP_VERSION` is baked into the image (`ARG` / `ENV`) and returned by `/api/health`.

## 3. Configuration (environment)

See `.env.example` — key variables:

- **`OPERATOR_ENV`**: set to `production` to hide internal error details from JSON clients (generic `internal_server_error`).
- **`OPERATOR_CORS_ORIGINS`**: comma-separated list; avoid `*` in production if browsers hit the API cross-origin.
- **`OPERATOR_CSP`**: optional `Content-Security-Policy` on **responses** (mostly API); static HTML still loads ECharts from CDN unless you self-host.
- **`OPERATOR_PG_CONNECT_TIMEOUT_S`**, **`OPERATOR_PG_APPLICATION_NAME`**: observability and resilience.
- **`OPERATOR_SILENCE_HEALTH_LOGS`**: suppresses successful access-log lines for `/api/health` and `/api/health/ready` (default `1`).

Postgres connectivity uses existing **`PGHOST`**, **`PGUSER`**, **`PGPASSWORD`**, **`PGDATABASE`** (set by Compose to the internal `postgres` service).

## 4. Security behavior

- **Security headers** on all responses: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`; optional CSP via `OPERATOR_CSP`.
- **`X-Request-ID`**: generated or echoed for each request; included in access logs.
- **GZip** middleware for responses above ~1 KB.
- **Container user**: non-root `appuser` (uid **10001**).

## 5. Validation

```bash
./scripts/smoke.sh
```

Smoke waits on **`/api/health/ready`**, then probes pages and API contracts. For a minimal CI job:

```bash
OPERATOR_SMOKE_HEALTH_ONLY=1 ./scripts/smoke.sh
```

## 6. Reverse proxy

Uvicorn is started with **`--proxy-headers`**. Terminate TLS at nginx/traefik and forward `X-Forwarded-Proto` / `Host` as appropriate. Restrict **8090** on the host firewall if operators reach the VM on a shared LAN (Compose publishes `127.0.0.1:8090` by default).

## 7. Corporate / locked-down workstations (no host admin)

- Charts use **vendored ECharts** at `/vendor/echarts.min.js` (bundled in the image/repo). Browsers never need to reach a public CDN. Refresh with **`./scripts/vendor_operator_echarts.sh`** on a networked machine if you upgrade versions.
- Run the stack in a **VM** or **Docker** on the machine you control; bind ports to **127.0.0.1** (Compose default for operator) and use **SSH port forwarding** from your laptop if policy blocks LAN access.
- Default **Content-Security-Policy** is set in-app (`script-src 'self' 'unsafe-inline'` …) so the UI works without external script hosts. Override with **`OPERATOR_CSP`** only if you know the implications.
- **Rate limiting** is optional (`OPERATOR_RATE_LIMIT_PER_MINUTE`, default 360/min per IP for `/api/*`, health excluded). It is **in-memory** and best suited to a **single worker** process.

## 8. Known limits

- APIs are **read-only**; schedule semantics remain in SQL views.
- Heuristic panels (finish cone, scenario sandbox) are **not** CPM-authoritative.
- Brand image path (`OPERATOR_BRAND_IMAGE_PATH`) must be readable inside the container if used.
- **`robots.txt`** returns `Disallow: /` (internal tool; not for public indexing).
