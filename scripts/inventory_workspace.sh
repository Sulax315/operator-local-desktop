#!/usr/bin/env bash
# List sibling prototype repos and cleanup candidates. Read-only.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE="$(cd "$REPO_ROOT/.." && pwd)"

echo "=== Bratek Operator Stack (Clean Edition) — workspace inventory ==="
echo "This repo:     $REPO_ROOT"
echo "Workspace root: $WORKSPACE"
echo ""

EXPECTED=(
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
  operator-stack-clean
)

echo "=== Expected project trees (existence) ==="
for name in "${EXPECTED[@]}"; do
  path="$WORKSPACE/$name"
  if [[ -d "$path" ]]; then
    echo "FOUND:    $name"
  else
    echo "MISSING:  $name"
  fi
done

echo ""
echo "=== Candidate ARCHIVE folders (whole trees → dated archive) ==="
ARCHIVE_CANDIDATES=(
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
for name in "${ARCHIVE_CANDIDATES[@]}"; do
  path="$WORKSPACE/$name"
  [[ -d "$path" ]] && echo "$path"
done

echo ""
echo "=== Candidate DELETE folders (after archive verified — destructive) ==="
DELETE_CANDIDATES=(
  ProfitIntel
  NotesSummary
  FinanceOS
  ScheduleOS
)
for name in "${DELETE_CANDIDATES[@]}"; do
  path="$WORKSPACE/$name"
  [[ -d "$path" ]] && echo "$path"
done
echo "(Also consider deleting root 'docs' if empty.)"

echo ""
echo "=== Other top-level directories (not in expected list) ==="
shopt -s nullglob
for path in "$WORKSPACE"/*; do
  [[ -d "$path" ]] || continue
  base="$(basename "$path")"
  skip=false
  for e in "${EXPECTED[@]}"; do
    [[ "$base" == "$e" ]] && skip=true && break
  done
  if [[ "$skip" == false ]]; then
    echo "$path"
  fi
done
shopt -u nullglob

echo ""
echo "Done. No files were modified."
