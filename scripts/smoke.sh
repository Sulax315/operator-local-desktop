#!/usr/bin/env bash
# Phase 1 smoke checks — read-only HTTP probes + compose validation. No rm/mv.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FAIL=0

echo "=== Bratek Operator Stack Phase 1 smoke ==="

if [[ ! -f .env ]]; then
  echo "FAIL: missing .env (copy .env.example to .env and set secrets)"
  exit 1
fi

if ! docker compose config >/dev/null 2>&1; then
  echo "FAIL: docker compose config (is .env present and valid?)"
  exit 1
fi
echo "PASS: docker compose config"

check_http() {
  local name="$1" url="$2"
  local code
  code="$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 3 --max-time 10 "$url" || echo "000")"
  if [[ "$code" =~ ^(2|3)[0-9][0-9]$ ]]; then
    echo "PASS: $name (HTTP $code $url)"
  else
    echo "FAIL: $name (HTTP $code $url)"
    FAIL=1
  fi
}

check_http "metabase" "http://127.0.0.1:8082/"
check_http "n8n" "http://127.0.0.1:8083/"

if [[ "$FAIL" -ne 0 ]]; then
  echo "=== RESULT: FAIL ==="
  exit 1
fi

echo "=== RESULT: PASS ==="
exit 0
