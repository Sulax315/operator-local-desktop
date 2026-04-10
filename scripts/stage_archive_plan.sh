#!/usr/bin/env bash
# Print mkdir + mv commands to archive prototype folders. DRY-RUN: prints only (default).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE="$(cd "$REPO_ROOT/.." && pwd)"

STAMP="$(date +%Y-%m-%d)"
ARCHIVE_DIR="$WORKSPACE/archive/$STAMP-prototype-snapshot"

FOLDERS=(
  ControlTower
  mcp_gateway
  action-desk
  WorkOS
  profitintel-analytics-workspace
  ProfitIntel
  NotesSummary
  profit-forensics
  meeting_intelligence
  ScheduleLab
  ScheduleOS
  FinanceOS
)

echo "================================================================"
echo " ARCHIVE PLAN (dry-run — no commands executed by this script)"
echo " Workspace: $WORKSPACE"
echo " Archive:   $ARCHIVE_DIR"
echo "================================================================"
echo ""
echo "mkdir -p \"$ARCHIVE_DIR\""
echo ""

for name in "${FOLDERS[@]}"; do
  src="$WORKSPACE/$name"
  if [[ -d "$src" ]]; then
    echo "mv \"$src\" \"$ARCHIVE_DIR/$name\""
  else
    echo "# skip (missing): $src"
  fi
done

echo ""
echo "# Optional: move root docs/ if present and worth keeping"
if [[ -d "$WORKSPACE/docs" ]]; then
  echo "mv \"$WORKSPACE/docs\" \"$ARCHIVE_DIR/docs-workspace-root\""
else
  echo "# no $WORKSPACE/docs"
fi

echo ""
echo "----------------------------------------------------------------"
echo " operator-stack-clean is NOT listed — keep it at workspace root."
echo " Review the lines above, then run manually from Git Bash/WSL."
echo "----------------------------------------------------------------"
