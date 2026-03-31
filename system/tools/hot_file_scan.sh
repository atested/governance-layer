#!/bin/bash
set -euo pipefail

hot_regex='^(system/scripts/release-gate\.sh|system/scripts/validate-proof-bundle\.sh|system/scripts/codex-unattended\.sh|docs/dev/WORK_QUEUE\.md|docs/dev/ASSIGNMENTS\.md)$'

if [[ $# -ne 1 ]]; then
  echo "usage: hot_file_scan.sh <file_list_path>" >&2
  exit 2
fi

list_file="$1"
if [[ ! -f "$list_file" ]]; then
  echo "missing file list: $list_file" >&2
  exit 1
fi

hits=$(LC_ALL=C sort "$list_file" | rg -n "$hot_regex" || true)
if [[ -n "$hits" ]]; then
  echo "HOT_FILE_SCAN:FAIL"
  echo "$hits" | sed 's/^/HOT:/'
  exit 1
fi

echo "HOT_FILE_SCAN:PASS"
exit 0
