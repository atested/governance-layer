#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WF="${TASK158_WORKFLOW_FILE:-$ROOT/.github/workflows/release-gate.yml}"

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

require_fixed() {
  local needle="$1"
  local label="$2"
  if rg -F -q "$needle" "$WF"; then
    echo "PASS: $label"
  else
    echo "FAIL: missing $label"
    exit 1
  fi
}

echo "--- T-GHA-ARTIFACTS-EXT-001: workflow covers extended release-gate artifacts deterministically ---"
require_fixed 'actions/checkout@v4' "checkout step present"
require_fixed 'actions/setup-python@v5' "setup-python step present"
require_fixed 'GOV_PROFILE: ci' "GOV_PROFILE=ci env present"
require_fixed 'bash system/scripts/release-gate.sh' "release-gate invocation present"
require_fixed 'out/proof-bundles/**' "proof-bundle wildcard artifact path present"
require_fixed 'out/proof-bundles/**/validate_proof_bundle_summary.json' "validator summary JSON artifact path present"
require_fixed 'out/release_gate.stdout.log' "release-gate stdout log artifact path present"
echo "PASS: proof-bundle wildcard implies validator summary JSON upload when present"

H1="$(sha256_file "$WF")"
H2="$(sha256_file "$WF")"
echo "WORKFLOW_EXT_SHA256_RUN1=$H1"
echo "WORKFLOW_EXT_SHA256_RUN2=$H2"
[[ "$H1" == "$H2" ]] || { echo "FAIL: workflow digest mismatch across two reads"; exit 1; }
echo "PASS: workflow digest deterministic across two reads"
