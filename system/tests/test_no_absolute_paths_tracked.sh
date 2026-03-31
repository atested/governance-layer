#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

tmp_all="$(mktemp)"
tmp_bad="$(mktemp)"
trap 'rm -f "$tmp_all" "$tmp_bad"' EXIT

# Known intentional references retained for docs, fixtures, and legacy tooling.
ALLOW_RE='^(LOGS/|docs/|tests/|system/tests/|schemas/|capabilities/|mcp/|scripts/append-record-runtime.sh$|system/scripts/cecil-runloop.sh$|system/scripts/merge-queue.sh$|system/scripts/task-watermark.sh$)'

git ls-files -z | xargs -0 rg -n -H '/Users/|/Volumes/' > "$tmp_all" || true
if [[ ! -s "$tmp_all" ]]; then
  echo "CASE=NO_ABSOLUTE_PATHS_TRACKED PASS"
  exit 0
fi

awk -F: '{print $1":"$2}' "$tmp_all" | sort -u | while IFS= read -r fl; do
  f="${fl%%:*}"
  if [[ ! "$f" =~ $ALLOW_RE ]]; then
    echo "$fl"
  fi
done | sort -u > "$tmp_bad"

if [[ -s "$tmp_bad" ]]; then
  cat "$tmp_bad"
  echo "FAIL:ABSOLUTE_PATHS_FOUND"
  exit 1
fi

echo "CASE=NO_ABSOLUTE_PATHS_TRACKED PASS"
