#!/usr/bin/env bash
set -euo pipefail

STACK_DIR="${STACK_DIR:-/app/workos}"
COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.prod.yml}"
BACKUP_DIR="${1:-/app/backups/workos}"

cd "$STACK_DIR"

backend_container="$(docker-compose -f "$COMPOSE_FILE" ps -q backend)"
if [[ -z "$backend_container" ]]; then
    echo "WorkOS backend container is not running." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
docker exec \
    -e WORK_OS_BACKUP_DIR=/backups \
    -i "$backend_container" \
    python -m ops.backup_database --backup-dir /backups >/tmp/workos-backup-path.txt

container_backup="$(cat /tmp/workos-backup-path.txt)"
host_backup="${BACKUP_DIR%/}/$(basename "$container_backup")"

docker cp "$backend_container:$container_backup" "$host_backup"
rm -f /tmp/workos-backup-path.txt

echo "$host_backup"
