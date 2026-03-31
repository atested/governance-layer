#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/in.txt" <<'EOF'
noise
REASON_CODE=HASH_NOT_FOUND
more
ADMISSIBLE=NO
STOP_REQUIRED=NO
EOF

out="$(system/scripts/foundation-v0-admissibility-normalize.sh "$tmp/in.txt")"
printf '%s\n' "$out" | sed -n '1p' | rg '^ADMISSIBLE=NO$' >/dev/null
printf '%s\n' "$out" | sed -n '2p' | rg '^STOP_REQUIRED=NO$' >/dev/null
printf '%s\n' "$out" | sed -n '3p' | rg '^REASON_CODE=HASH_NOT_FOUND$' >/dev/null

echo "PASS test_foundation_v0_admissibility_normalize"
