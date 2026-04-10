#!/usr/bin/env bash
# Print rm -rf commands for DELETE candidates. DRY-RUN ONLY — never executes deletes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE="$(cd "$REPO_ROOT/.." && pwd)"

echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
echo " DELETE PLAN — DESTRUCTIVE — NOT EXECUTED BY THIS SCRIPT"
echo " Only run these AFTER a verified archive/tarball exists."
echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
echo ""

DELETE_AFTER_ARCHIVE=(
  ProfitIntel
  NotesSummary
  FinanceOS
  ScheduleOS
)

for name in "${DELETE_AFTER_ARCHIVE[@]}"; do
  target="$WORKSPACE/$name"
  if [[ -d "$target" ]]; then
    echo "rm -rf \"$target\""
  else
    echo "# skip (missing): $target"
  fi
done

echo ""
echo "# Optional empty junk:"
echo "# rmdir \"$WORKSPACE/docs\" 2>/dev/null   # only if empty and unwanted"

echo ""
echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
echo " NEVER delete: operator-stack-clean"
echo " NEVER delete: archive/ until you have off-host backup"
echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
