# Environment contract examples

## Source

| File | Origin |
|------|--------|
| `mcp-gateway.env.example` | `mcp_gateway/.env.example` |
| `backend.env.example` | `action-desk/infra/env/backend.env.example` |
| `frontend.env.example` | `action-desk/infra/env/frontend.env.example` |
| `postgres.env.example` | `action-desk/infra/env/postgres.env.example` |
| `workos-loopback-compose.env.example` | `WorkOS/deploy/env.production.example` |

## Why extracted

Shows **variable naming** and **integration points** (DB URL, public URL, OAuth redirect, TLS-related gateway vars) without pulling application code.

## Reuse

Copy keys you need into a new `.env.example` for your product; rename prefixes to match your app.

## Confidence

**High** as documentation of patterns. **Not** valid production values.
