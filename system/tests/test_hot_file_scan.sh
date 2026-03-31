#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

printf 'docs/spec/process-ledger-v1.md\n' > "$tmp_dir/pass.txt"
"$repo_root/system/tools/hot_file_scan.sh" "$tmp_dir/pass.txt"

printf 'docs/spec/process-ledger-v1.md\nsystem/scripts/release-gate.sh\n' > "$tmp_dir/fail.txt"
set +e
"$repo_root/system/tools/hot_file_scan.sh" "$tmp_dir/fail.txt" > "$tmp_dir/fail.out" 2>&1
rc=$?
set -e
if [[ "$rc" -eq 0 ]]; then
  echo "expected hot-file scan failure"
  exit 1
fi

echo "TEST_HOT_FILE_SCAN:PASS"
