#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task159-kv-ordering.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

assert_sorted_no_dups() {
  python3 - <<'PY' "$1" "$2"
import sys
from pathlib import Path
p=Path(sys.argv[1]); label=sys.argv[2]
keys=[]
for line in p.read_text(encoding="utf-8").splitlines():
    if "=" not in line:
        raise SystemExit(f"FAIL: {label} missing_equals")
    if " = " in line or line.startswith(" ") or line.endswith(" "):
        raise SystemExit(f"FAIL: {label} spaces_around_equals")
    k,_=line.split("=",1)
    if not k:
        raise SystemExit(f"FAIL: {label} empty_key")
    keys.append(k)
if len(keys) != len(set(keys)):
    raise SystemExit(f"FAIL: {label} duplicate_key")
if keys != sorted(keys):
    raise SystemExit(f"FAIL: {label} unsorted_keys")
print(f"PASS: {label} canonical key ordering")
print(f"PASS: {label} duplicate keys absent")
PY
}

run_gate() {
  local run_id="$1"
  RELEASE_GATE_SKIP_BASE=1 GOV_PROFILE=dev RELEASE_GATE_RUN_ID="$run_id" RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$TMPDIR_LOCAL/out/proof-bundles" \
    bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/$run_id.out"
}

echo "--- T-KV-ORDER-001: versions.txt and release_gate_log.txt canonical ordering deterministic ---"
run_gate run1
run_gate run2
b1="$TMPDIR_LOCAL/out/proof-bundles/run1"
b2="$TMPDIR_LOCAL/out/proof-bundles/run2"
assert_sorted_no_dups "$b1/versions.txt" "versions.txt"
assert_sorted_no_dups "$b1/release_gate_log.txt" "release_gate_log.txt"
V1="$(sha256_file "$b1/versions.txt")"; V2="$(sha256_file "$b2/versions.txt")"
L1="$(sha256_file "$b1/release_gate_log.txt")"; L2="$(sha256_file "$b2/release_gate_log.txt")"
[[ "$V1" == "$V2" ]] || { echo "FAIL: versions.txt nondeterministic"; exit 1; }
[[ "$L1" == "$L2" ]] || { echo "FAIL: release_gate_log.txt nondeterministic"; exit 1; }
echo "VERSIONS_ORDER_SHA256_RUN1=$V1"
echo "VERSIONS_ORDER_SHA256_RUN2=$V2"
echo "RELEASE_GATE_LOG_ORDER_SHA256_RUN1=$L1"
echo "RELEASE_GATE_LOG_ORDER_SHA256_RUN2=$L2"
echo "PASS: canonical ordering outputs deterministic across two runs"

