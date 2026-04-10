# Backup / restore scripts (SQLite via container)

## Source

`c:\Dev\WorkOS\deploy\backup-workos-sqlite.sh`  
`c:\Dev\WorkOS\deploy\restore-workos-sqlite.sh`

## Why extracted

Concrete pattern: **docker exec** into backend → Python module writes backup → **docker cp** to host.

## Reuse

Edit `STACK_DIR`, `COMPOSE_FILE`, container service names, and paths inside the scripts. Prefer `docker compose` over legacy `docker-compose` if your hosts are modern.

## Confidence

**Medium**: logic is sound; **hardcoded** assumptions bind these scripts to WorkOS’s layout unless edited.
