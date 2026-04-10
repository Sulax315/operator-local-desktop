#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: bash deploy/restore-workos-sqlite.sh /path/to/workos_backup.sqlite3" >&2
    exit 1
fi

backup_file="$1"
if [[ ! -f "$backup_file" ]]; then
    echo "Backup file not found: $backup_file" >&2
    exit 1
fi

STACK_DIR="${STACK_DIR:-/app/workos}"
COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.prod.yml}"

cd "$STACK_DIR"

backend_container="$(docker-compose -f "$COMPOSE_FILE" ps -q backend)"
if [[ -z "$backend_container" ]]; then
    echo "Unable to locate the WorkOS backend container." >&2
    exit 1
fi

volume_name="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}' "$backend_container")"
if [[ -z "$volume_name" ]]; then
    echo "Unable to locate the WorkOS data volume." >&2
    exit 1
fi

volume_path="$(docker volume inspect -f '{{ .Mountpoint }}' "$volume_name")"
if [[ -z "$volume_path" ]]; then
    echo "Unable to resolve the WorkOS data volume mountpoint." >&2
    exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
current_db="$volume_path/work_os.sqlite3"
rollback_copy="$volume_path/work_os.pre_restore_${timestamp}.sqlite3"

docker-compose -f "$COMPOSE_FILE" stop frontend backend

if [[ -f "$current_db" ]]; then
    cp "$current_db" "$rollback_copy"
fi

install -m 600 "$backup_file" "$current_db"

docker-compose -f "$COMPOSE_FILE" up -d backend frontend

echo "Restored $backup_file to $current_db"
if [[ -f "$rollback_copy" ]]; then
    echo "Previous database saved at $rollback_copy"
fi
