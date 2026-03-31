#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/b"
cat > "$tmp/b/proof_manifest.json" <<'JSON'
{"coverage_stamp_ref":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
JSON
cat > "$tmp/b/ledger.jsonl" <<'JSONL'
{"capability_surfaces":["shell","filesystem"]}
JSONL

out="$(system/scripts/foundation-v0-bundle-probe.sh "$tmp/b")"
printf '%s\n' "$out" | rg '^MANIFEST_PATH=' >/dev/null
printf '%s\n' "$out" | rg '^DETECTED_SURFACES=filesystem,shell$' >/dev/null
printf '%s\n' "$out" | rg '^LEDGER_PATH=' >/dev/null

echo "PASS test_foundation_v0_bundle_probe"
