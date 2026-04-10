# Reference-only materials

## Rule

**Do not** wire these into automated builds as dependencies. Read for ideas, then reimplement or rewrite for your stack.

## Contents

| File | Source | Purpose |
|------|--------|---------|
| `controltower-deploy-pack-README.md` | Control Tower `infra/deploy/controltower/README.md` | systemd + `/srv` + nginx + cron mental model for loopback Python |
| `controltower-nginx-loopback-proxy.tpl` | Control Tower nginx template | Parameterized reverse proxy to single backend |
| `profit-forensics-architecture.md` | profit-forensics `docs/architecture.md` | Ingestion/runtime directory layout and Docker framing |

## Confidence

**Medium** for operator layout ideas. **Low** as executable truth—prototypes may be stale relative to any real host.
