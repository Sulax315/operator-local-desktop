# Bratek Operator Stack (Clean Edition)

This repository is a **clean restart foundation**. It exists to hold **small, reusable operator patterns** extracted from a prior prototype workspace—not to preserve legacy products, domains, or full applications.

## What this is

- **Starter assets** only: nginx examples, compose skeletons, MCP edge reference, backup scripts, env contracts, and a few reference documents.
- **No application code** beyond a self-contained bearer-auth sidecar used by the MCP edge pattern.
- **No production deployment** is defined here yet.

## What this is not

- Not a monorepo of Control Tower, WorkOS, ProfitIntel, or any other retired prototype.
- Not a source of truth for `*.bratek.io` routing (examples may still mention old hostnames for traceability).

## Layout

| Path | Purpose |
|------|---------|
| `docs/` | Salvage inventory, migration decisions, repo architecture notes |
| `starter-assets/` | Copy-paste or adapt when building real infra |
| `scripts/` | **Dry-run** workspace inventory and cleanup staging (no deletes by default) |

## Next steps

1. Review `docs/migration_decisions.md` and `docs/salvage_inventory.md`.
2. Run `bash scripts/inventory_workspace.sh` from this repo root (Git Bash / WSL).
3. After human review, use `stage_archive_plan.sh` / `stage_delete_plan.sh` only as printed command lists against the **parent** workspace—then execute moves/deletes manually if approved.

## Conventions

- Prefer **generic** hostnames and paths when adapting examples.
- Treat everything under `starter-assets/reference-only/` as **read-only inspiration**, not dependencies.
