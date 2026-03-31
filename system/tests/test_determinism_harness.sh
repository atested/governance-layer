#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

cat > "$tmp_dir/a.txt" <<'EOT'
/tmp/run-111/path value   
line two   
EOT
cat > "$tmp_dir/b.txt" <<'EOT'
/tmp/run-222/path value
line two
EOT

out1="$($repo_root/system/tools/determinism_harness.sh "$tmp_dir/a.txt")"
out2="$($repo_root/system/tools/determinism_harness.sh "$tmp_dir/b.txt")"
sha1="$(echo "$out1" | awk '{print $1}')"
sha2="$(echo "$out2" | awk '{print $1}')"
if [[ "$sha1" != "$sha2" ]]; then
  echo "normalized hashes differ"
  exit 1
fi

echo "TEST_DETERMINISM_HARNESS:PASS"
