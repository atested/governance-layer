#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task155-ci-contract-suite.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

run_once() {
  local out="$1"
  GOV_PROFILE=ci \
  RELEASE_GATE_SKIP_BASE=1 \
  RELEASE_GATE_RUN_ID=fixed-ci-contract \
  RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$TMPDIR_LOCAL/out/proof-bundles" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$out"
}

echo "--- T-RELEASE-GATE-CI-SUITE-001: ci profile runs full contract suite deterministically ---"
run_once "$TMPDIR_LOCAL/run1.out"
run_once "$TMPDIR_LOCAL/run2.out"

for f in "$TMPDIR_LOCAL/run1.out" "$TMPDIR_LOCAL/run2.out"; do
  grep -q '## External CI Contract Checks (GOV_PROFILE=ci)' "$f"
  grep -q 'T-CONTRACT-001: proof-packet manifest/summary/sha contracts enforced and deterministic' "$f"
  grep -q 'T-AUXFMT-001: versions.txt and release_gate_log.txt key=value format contract' "$f"
  grep -q 'T-PROOF-BUNDLE-CONTRACT-001: required files + checksum pass deterministically' "$f"
done

D1="$(sha256_file "$TMPDIR_LOCAL/run1.out")"
D2="$(sha256_file "$TMPDIR_LOCAL/run2.out")"
[[ "$D1" == "$D2" ]] || { echo "FAIL: ci contract suite transcript nondeterministic"; exit 1; }

echo "CI_CONTRACT_SUITE_SHA256_RUN1=$D1"
echo "CI_CONTRACT_SUITE_SHA256_RUN2=$D2"
echo "PASS: ci profile runs proof-packet core/aux/required-file contract suite deterministically"

