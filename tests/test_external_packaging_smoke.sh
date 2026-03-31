#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp_root="${TMPDIR:-/tmp}"
tmp_root="${tmp_root%/}"
tmp_dir="$(mktemp -d "${tmp_root}/task168-packaging-smoke.XXXXXX")"
trap 'rm -rf "$tmp_dir"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

run_once() {
  local out="$1"
  {
    echo "--- T-EXTERNAL-PACKAGING-SMOKE-001: packaging file/doc smoke deterministic ---"
    local status
    status="$(git -C "$ROOT" status --porcelain || true)"
    if [[ -n "$status" ]]; then
      echo "INFO: git status dirty (non-fatal packaging smoke)"
    else
      echo "INFO: git status clean"
    fi

    local required=(
      "README.md"
      "docs/EXTERNAL_CONTRACTS.md"
      "docs/TEST-SUITE.md"
      "system/scripts/bootstrap-run.sh"
      "system/scripts/release-gate.sh"
    )
    for f in "${required[@]}"; do
      [[ -f "$ROOT/$f" ]] || { echo "FAIL: missing required file: $f"; exit 1; }
      echo "PASS: required file present: $f"
    done

    rg -n "proof_packet\\.tar|proof_packet_verify_summary\\.json|proof_packet\\.sha256|release_gate_log\\.txt|versions\\.txt" \
      "$ROOT/README.md" "$ROOT/docs/EXTERNAL_CONTRACTS.md" "$ROOT/docs/DISTRIBUTION.md" "$ROOT/docs/TEST-SUITE.md" \
      | LC_ALL=C sort > "$tmp_dir/docs_scan.tmp"
    if [[ ! -s "$tmp_dir/docs_scan.tmp" ]]; then
      echo "FAIL: docs proof-bundle references missing"
      exit 1
    fi
    cat "$tmp_dir/docs_scan.tmp"
    echo "PASS: docs proof-bundle references present"

    rg -n "queue_drift_scan\\.txt|queue_drift_scan\\.json|status_bundle\\.json" \
      "$ROOT/docs/EXTERNAL_CONTRACTS.md" "$ROOT/docs/DISTRIBUTION.md" \
      | LC_ALL=C sort > "$tmp_dir/docs_optional_scan.tmp"
    if [[ ! -s "$tmp_dir/docs_optional_scan.tmp" ]]; then
      echo "FAIL: docs optional proof-bundle references missing"
      exit 1
    fi
    cat "$tmp_dir/docs_optional_scan.tmp"
    echo "PASS: docs optional proof-bundle references present"
  } > "$out"
}

run_once "$tmp_dir/run1.out"
run_once "$tmp_dir/run2.out"
D1="$(sha256_file "$tmp_dir/run1.out")"
D2="$(sha256_file "$tmp_dir/run2.out")"
cat "$tmp_dir/run1.out"
echo "EXTERNAL_PACKAGING_SMOKE_SHA256_RUN1=$D1"
echo "EXTERNAL_PACKAGING_SMOKE_SHA256_RUN2=$D2"
[[ "$D1" == "$D2" ]] || { echo "FAIL: packaging smoke output nondeterministic"; exit 1; }
echo "PASS: external packaging smoke output deterministic across two runs"
