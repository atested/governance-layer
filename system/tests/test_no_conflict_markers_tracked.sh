#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

set +e
git ls-files -z | xargs -0 rg -n -H -e '^<<<<<<<' -e '^=======$' -e '^>>>>>>>' > "$tmp"
rc=$?
set -e

if [[ "$rc" -eq 0 ]]; then
  sort -u "$tmp"
  echo "FAIL:CONFLICT_MARKERS_FOUND"
  exit 1
fi

if [[ "$rc" -eq 1 ]]; then
  echo "CASE=NO_CONFLICT_MARKERS_TRACKED PASS"
  exit 0
fi

echo "FAIL:SCAN_ERROR"
exit 1
