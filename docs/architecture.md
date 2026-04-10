# Repository architecture (Clean Edition)

## Scope boundary

This repo intentionally contains **no product application** (no Next.js app tree, no Control Tower Python package, no validators). It holds **operator-facing building blocks** and **documentation** for a future Bratek operator stack.

## Component map

```
operator-stack-clean/
├── README.md                 # Entry point and rules
├── docs/                     # Human decisions and inventories
├── starter-assets/           # Extracted patterns (not runnable end-to-end alone)
│   ├── mcp-edge/             # TLS edge + nginx + compose reference + auth sidecar
│   ├── nginx/                # Host nginx: split UI / API paths
│   ├── compose/              # Loopback-published app stack example
│   ├── scripts/              # SQLite backup/restore (adapt container names)
│   ├── env/                  # Env contract examples
│   └── reference-only/       # Non-executable reference text
└── scripts/                  # Workspace listing / dry-run cleanup plans
```

## Design rules

1. **Reference-only** material must never be imported as code dependencies.
2. **Examples** may contain old hostnames; replace before any real edge.
3. **MCP edge** `docker-compose.yml` expects additional service build contexts that were **not** copied—trim or supply your own images before `docker compose up`.
4. Future “real” operator stack work should live in **new** directories (e.g. `infra/`, `services/`) with clear ownership—**not** by growing `starter-assets/` indefinitely.
