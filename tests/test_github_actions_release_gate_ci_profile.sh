#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WF="${TASK147_WORKFLOW_FILE:-$ROOT/.github/workflows/release-gate.yml}"

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

echo "--- T-GHA-CI-PROFILE-001: workflow contains required CI gating steps and artifact paths ---"
require_fixed 'actions/checkout@v4' "checkout step present"
require_fixed 'actions/setup-python@v5' "setup-python step present"
require_fixed 'GOV_PROFILE=ci bash system/scripts/release-gate.sh' "explicit GOV_PROFILE=ci release-gate invocation present"
require_fixed 'out/proof-bundles/**' "proof-bundle artifact path present"
require_fixed 'out/release_gate.stdout.log' "release-gate stdout log artifact path present"

H1="$(sha256_file "$WF")"
H2="$(sha256_file "$WF")"
echo "WORKFLOW_SHA256_RUN1=$H1"
echo "WORKFLOW_SHA256_RUN2=$H2"
[[ "$H1" == "$H2" ]] || { echo "FAIL: workflow digest mismatch across two reads"; exit 1; }
echo "PASS: workflow digest deterministic across two reads"

echo "Summary: GitHub Actions release-gate CI profile workflow sanity checks complete"
