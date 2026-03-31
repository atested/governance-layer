#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task156-ci-validator.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

normalize_ci_validator_block() {
  local in_file="$1" out_file="$2"
  python3 - <<'PY' "$in_file" "$out_file"
import re, sys
from pathlib import Path
inp = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
out = []
capture = False
for line in inp:
    if line.startswith("## External CI Proof-Bundle Validation (GOV_PROFILE=ci)"):
        capture = True
    if capture:
        line = re.sub(r'/tmp/[^ ]+', '/tmp/<PATH>', line)
        line = re.sub(r'/var/folders/[^ ]+', '/var/folders/<PATH>', line)
        out.append(line)
    if capture and line.startswith("INFO: external proof-bundle validator pass"):
        break
Path(sys.argv[2]).write_text("\n".join(out) + "\n", encoding="utf-8")
PY
}

run_once() {
  local run_id="$1" out_file="$2"
  set +e
  GOV_PROFILE=ci \
  RELEASE_GATE_SKIP_BASE=1 \
  RELEASE_GATE_RUN_ID="$run_id" \
  RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$TMPDIR_LOCAL/out/proof-bundles" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$out_file" 2>&1
  local rc=$?
  set -e
  echo "$rc"
}

echo "--- T-RELEASE-GATE-CI-VALIDATOR-001: ci profile runs external validator deterministically ---"
RC1="$(run_once run1 "$TMPDIR_LOCAL/run1.out")"
RC2="$(run_once run2 "$TMPDIR_LOCAL/run2.out")"
[[ "$RC1" == "0" ]] || { echo "FAIL: run1 expected rc=0 got $RC1"; exit 1; }
[[ "$RC2" == "0" ]] || { echo "FAIL: run2 expected rc=0 got $RC2"; exit 1; }
for f in "$TMPDIR_LOCAL/run1.out" "$TMPDIR_LOCAL/run2.out"; do
  grep -q '## External CI Proof-Bundle Validation (GOV_PROFILE=ci)' "$f"
  grep -q '\$ bash system/scripts/validate-proof-bundle.sh ' "$f"
  grep -q 'PASS: proof-bundle external contract valid' "$f"
  grep -q 'INFO: external proof-bundle validator pass' "$f"
done

normalize_ci_validator_block "$TMPDIR_LOCAL/run1.out" "$TMPDIR_LOCAL/run1.norm"
normalize_ci_validator_block "$TMPDIR_LOCAL/run2.out" "$TMPDIR_LOCAL/run2.norm"
D1="$(sha256_file "$TMPDIR_LOCAL/run1.norm")"
D2="$(sha256_file "$TMPDIR_LOCAL/run2.norm")"
[[ "$D1" == "$D2" ]] || { echo "FAIL: ci validator block nondeterministic"; exit 1; }
echo "CI_VALIDATOR_BLOCK_SHA256_RUN1=$D1"
echo "CI_VALIDATOR_BLOCK_SHA256_RUN2=$D2"
echo "PASS: ci profile external validator block deterministic across two runs"

