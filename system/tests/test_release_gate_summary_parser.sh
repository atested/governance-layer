#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

cat > "$tmp_dir/release_gate.log" <<'EOT'
PASS: check one
PASS: check two
FAIL: check three
[exit=1]
EOT

output="$($repo_root/system/tools/release_gate_summary_parser.sh "$tmp_dir/release_gate.log")"
echo "$output" | rg '^PASS_LINES=2$' >/dev/null
echo "$output" | rg '^FAIL_LINES=1$' >/dev/null
echo "$output" | rg '^EXIT=1$' >/dev/null

echo "TEST_RELEASE_GATE_SUMMARY_PARSER:PASS"
