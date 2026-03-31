#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/merge-helpers-noninteractive.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

FILES=(
  "system/scripts/cecil-runloop.sh"
  "system/scripts/merge-queue.sh"
  "system/scripts/queue-claim.sh"
  "system/scripts/queue-list-next.sh"
  "system/scripts/task-watermark.sh"
)

PATTERN='Do you want to proceed|read -p|Proceed to .*(yes/no)|\\(yes/no\\)|^[[:space:]]*select[[:space:]]|Press any key'

echo "SCAN_FILES_BEGIN"
for f in "${FILES[@]}"; do
  echo "$f"
done
echo "SCAN_FILES_END"

set +e
rg -n -H -S "$PATTERN" "${FILES[@]/#/$ROOT/}" | LC_ALL=C sort > "$TMPDIR_LOCAL/hits.txt"
RC=$?
set -e

if [ "$RC" -eq 0 ]; then
  echo "FAIL: interactive prompt patterns detected"
  cat "$TMPDIR_LOCAL/hits.txt"
  exit 1
fi

if [ "$RC" -ne 1 ]; then
  echo "ERROR: scan command failed rc=$RC"
  exit 2
fi

echo "PASS: no interactive prompt patterns in merge helper scripts"
