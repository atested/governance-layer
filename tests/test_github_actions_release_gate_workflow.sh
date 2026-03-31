#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WF="$ROOT/.github/workflows/release-gate.yml"

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

echo "--- T-GHA-RELEASE-GATE-001: workflow file exists and has required steps/paths ---"
test -f "$WF"
grep -q '^name: release-gate$' "$WF"
grep -q 'actions/setup-python@v5' "$WF"
grep -q 'GOV_PROFILE: ci' "$WF"
grep -q 'bash system/scripts/release-gate.sh' "$WF"
grep -q 'actions/upload-artifact@v4' "$WF"
grep -q 'out/proof-bundles/\*\*' "$WF"
grep -q 'out/release_gate.stdout.log' "$WF"
echo "PASS: workflow contains checkout/python/ci-profile/release-gate/upload-artifact steps"

W1="$(sha256_file "$WF")"
W2="$(sha256_file "$WF")"
[[ "$W1" == "$W2" ]] || { echo "FAIL: workflow file digest mismatch"; exit 1; }
echo "WORKFLOW_SHA256_RUN1=$W1"
echo "WORKFLOW_SHA256_RUN2=$W2"
echo "PASS: workflow digest deterministic across repeated reads"
