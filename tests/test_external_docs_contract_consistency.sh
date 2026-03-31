#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
README_F="${TASK171_README_PATH:-$ROOT/README.md}"
EXTERNAL_F="${TASK171_EXTERNAL_CONTRACTS_PATH:-$ROOT/docs/EXTERNAL_CONTRACTS.md}"
DIST_F="${TASK171_DISTRIBUTION_PATH:-$ROOT/docs/DISTRIBUTION.md}"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task171-doc-consistency.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

require_ref() {
  local file="$1" needle="$2" label="$3"
  if rg -F -q "$needle" "$file"; then
    echo "PASS: $label"
  else
    echo "FAIL: $label"
    exit 1
  fi
}

run_once() {
  local out="$1"
  {
    echo "--- T-EXTERNAL-DOCS-CONSISTENCY-001: required/optional proof-bundle outputs documented consistently ---"
    if [[ ! -f "$DIST_F" ]]; then
      echo "INFO: docs/DISTRIBUTION.md missing (dependency TASK_166 not merged)"
      echo "SKIP: docs consistency enforcement deferred until DISTRIBUTION.md exists"
      return 3
    fi
    local required_files=(
      proof_packet.tar
      proof_packet_verify_summary.json
      proof_packet.sha256
      release_gate_log.txt
      versions.txt
    )
    local optional_files=(
      queue_drift_scan.txt
      queue_drift_scan.json
      status_bundle.json
    )
    local f
    for f in "${required_files[@]}"; do
      if rg -F -q "$f" "$README_F" || rg -F -q "$f" "$EXTERNAL_F"; then
        echo "PASS: required file referenced in README or EXTERNAL_CONTRACTS: $f"
      else
        echo "FAIL: missing required file reference in README/EXTERNAL_CONTRACTS: $f"
        exit 1
      fi
      require_ref "$DIST_F" "$f" "required file referenced in DISTRIBUTION: $f"
    done
    for f in "${optional_files[@]}"; do
      require_ref "$EXTERNAL_F" "$f" "optional file referenced in EXTERNAL_CONTRACTS: $f"
      require_ref "$DIST_F" "$f" "optional file referenced in DISTRIBUTION: $f"
    done
  } | tee "$out"
}

set +e
run_once "$TMPDIR_LOCAL/run1.out"
RC1=$?
run_once "$TMPDIR_LOCAL/run2.out"
RC2=$?
set -e
echo "RC_RUN1=$RC1"
echo "RC_RUN2=$RC2"
[[ "$RC1" == "$RC2" ]] || { echo "FAIL: inconsistent return codes across two runs"; exit 1; }
H1="$(sha256_file "$TMPDIR_LOCAL/run1.out")"
H2="$(sha256_file "$TMPDIR_LOCAL/run2.out")"
echo "DOCS_CONSISTENCY_SHA256_RUN1=$H1"
echo "DOCS_CONSISTENCY_SHA256_RUN2=$H2"
[[ "$H1" == "$H2" ]] || { echo "FAIL: docs consistency stdout nondeterministic"; exit 1; }
if [[ "$RC1" == "0" ]]; then
  echo "PASS: docs consistency check output deterministic across two runs"
  exit 0
fi
if [[ "$RC1" == "3" ]]; then
  echo "PASS: docs consistency SKIP output deterministic across two runs"
  exit 3
fi
echo "FAIL: unexpected docs consistency rc=$RC1"
exit 1
