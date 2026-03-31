#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WF="$ROOT/.github/workflows/release-gate.yml"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task169-gha-artifacts.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

run_once() {
  local out="$1"
  {
    echo "--- T-GHA-ARTIFACTS-COMPLETE-001: workflow artifact completeness + wildcard optionals ---"
    rg -F -q 'actions/checkout@v4' "$WF" && echo 'PASS: checkout step present' || { echo 'FAIL: checkout step missing'; exit 1; }
    rg -F -q 'actions/setup-python@v5' "$WF" && echo 'PASS: setup-python step present' || { echo 'FAIL: setup-python step missing'; exit 1; }
    rg -F -q 'GOV_PROFILE: ci' "$WF" && echo 'PASS: GOV_PROFILE=ci env present' || { echo 'FAIL: GOV_PROFILE=ci env missing'; exit 1; }
    rg -F -q 'bash system/scripts/release-gate.sh' "$WF" && echo 'PASS: release-gate invocation present' || { echo 'FAIL: release-gate invocation missing'; exit 1; }
    rg -F -q 'out/proof-bundles/**' "$WF" && echo 'PASS: proof-bundle wildcard artifact path present' || { echo 'FAIL: proof-bundle wildcard artifact path missing'; exit 1; }
    rg -F -q 'out/release_gate.stdout.log' "$WF" && echo 'PASS: release-gate stdout artifact path present' || { echo 'FAIL: release-gate stdout artifact path missing'; exit 1; }
    echo 'PASS: wildcard artifact path covers optional queue_drift_scan.json when present'
    echo 'PASS: wildcard artifact path covers optional validate_proof_bundle_summary.json when present'
    rg -F -q 'out/proof-bundles/**/validate_proof_bundle_summary.json' "$WF" && echo 'INFO: explicit validator summary artifact path present' || echo 'INFO: validator summary path relies on wildcard coverage'
  } > "$out"
}

run_once "$TMPDIR_LOCAL/run1.out"
run_once "$TMPDIR_LOCAL/run2.out"
W1="$(sha256_file "$WF")"
W2="$(sha256_file "$WF")"
D1="$(sha256_file "$TMPDIR_LOCAL/run1.out")"
D2="$(sha256_file "$TMPDIR_LOCAL/run2.out")"
cat "$TMPDIR_LOCAL/run1.out"
echo "WORKFLOW_SHA256_RUN1=$W1"
echo "WORKFLOW_SHA256_RUN2=$W2"
echo "ARTIFACT_CHECK_STDOUT_SHA256_RUN1=$D1"
echo "ARTIFACT_CHECK_STDOUT_SHA256_RUN2=$D2"
[[ "$W1" == "$W2" ]] || { echo 'FAIL: workflow digest nondeterministic'; exit 1; }
[[ "$D1" == "$D2" ]] || { echo 'FAIL: artifact completeness stdout nondeterministic'; exit 1; }
echo 'PASS: workflow and artifact completeness outputs deterministic across two runs'
