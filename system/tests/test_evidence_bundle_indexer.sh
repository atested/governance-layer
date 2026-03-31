#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
mkdir -p "$tmp_dir/evidence"
printf 'alpha\n' > "$tmp_dir/evidence/b.txt"
printf 'beta\n' > "$tmp_dir/evidence/a.txt"

out1="$($repo_root/system/tools/evidence_bundle_indexer.sh "$tmp_dir/evidence")"
out2="$($repo_root/system/tools/evidence_bundle_indexer.sh "$tmp_dir/evidence")"
sha1="$(printf '%s' "$out1" | shasum -a 256 | awk '{print $1}')"
sha2="$(printf '%s' "$out2" | shasum -a 256 | awk '{print $1}')"
[[ "$sha1" == "$sha2" ]]
echo "$out1" | rg '"path":"a.txt"' >/dev/null
echo "$out1" | rg '"path":"b.txt"' >/dev/null
line_a=$(echo "$out1" | rg -n '"path":"a.txt"' | cut -d: -f1)
line_b=$(echo "$out1" | rg -n '"path":"b.txt"' | cut -d: -f1)
[[ "$line_a" -lt "$line_b" ]]
echo "TEST_EVIDENCE_BUNDLE_INDEXER:PASS"
