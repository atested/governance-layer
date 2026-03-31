#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

printf 'a\nb\n' > "$tmp_dir/z.txt"
printf 'x\n' > "$tmp_dir/a.txt"

out="$($repo_root/system/tools/audit_artifact_helper.sh "$tmp_dir/z.txt" "$tmp_dir/a.txt")"
line1="$(echo "$out" | sed -n '1p' | awk -F'|' '{print $3}')"
line2="$(echo "$out" | sed -n '2p' | awk -F'|' '{print $3}')"
if [[ "$line1" > "$line2" ]]; then
  echo "output is not sorted"
  exit 1
fi

echo "TEST_AUDIT_ARTIFACT_HELPER:PASS"
