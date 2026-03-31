#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

out_ok="$($repo_root/system/tools/repo_tripwire.sh "$repo_root" "$repo_root/tests" 2>&1)"
echo "$out_ok" | rg '^TRIPWIRE_PASS$' >/dev/null

tmp_out="$(mktemp)"
set +e
$repo_root/system/tools/repo_tripwire.sh "$repo_root" /tmp > "$tmp_out" 2>&1
rc_fail=$?
set -e
[[ "$rc_fail" -eq 3 ]]
rg '^WRONG_EXECUTION_ROOT$' "$tmp_out" >/dev/null

rm -f "$tmp_out"
echo "TEST_REPO_TRIPWIRE:PASS"
