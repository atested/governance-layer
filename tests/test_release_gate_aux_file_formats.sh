#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task143-aux-formats.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

check_kv_file() {
  local file="$1" label="$2"
  python3 - <<'PY' "$file" "$label"
import sys
from pathlib import Path

path = Path(sys.argv[1]); label = sys.argv[2]
seen = {}
for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
    if not raw:
        continue
    if "=" not in raw:
        raise SystemExit(f"FAIL: {label} line {lineno} missing '='")
    if " = " in raw or raw.startswith("=") or raw.endswith("="):
        raise SystemExit(f"FAIL: {label} line {lineno} invalid spacing/empty side")
    key, value = raw.split("=", 1)
    if not key:
        raise SystemExit(f"FAIL: {label} line {lineno} empty key")
    if key.strip() != key or value.startswith(" "):
        raise SystemExit(f"FAIL: {label} line {lineno} spacing around '=' not allowed")
    if key in seen:
        raise SystemExit(f"FAIL: {label} duplicate key disallowed: {key}")
    seen[key] = value
print(f"PASS: {label} key=value contract valid")
print(f"PASS: {label} duplicate keys disallowed and none present")
PY
}

run_gate() {
  local run_id="$1"
  local out_base="$TMPDIR_LOCAL/out"
  RELEASE_GATE_SKIP_BASE=1 \
  GOV_PROFILE=dev \
  RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$out_base" \
  RELEASE_GATE_RUN_ID="$run_id" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/$run_id.release_gate.out"
  echo "$out_base/$run_id"
}

echo "--- T-AUXFMT-001: versions.txt and release_gate_log.txt key=value format contract ---"
OD1="$(run_gate run1)"
OD2="$(run_gate run2)"
check_kv_file "$OD1/versions.txt" "versions.txt"
check_kv_file "$OD1/release_gate_log.txt" "release_gate_log.txt"

V1="$(sha256_file "$OD1/versions.txt")"
V2="$(sha256_file "$OD2/versions.txt")"
L1="$(sha256_file "$OD1/release_gate_log.txt")"
L2="$(sha256_file "$OD2/release_gate_log.txt")"
[[ "$V1" == "$V2" ]] || { echo "FAIL: versions.txt digest mismatch"; exit 1; }
[[ "$L1" == "$L2" ]] || { echo "FAIL: release_gate_log.txt digest mismatch"; exit 1; }
echo "VERSIONS_TXT_SHA256_RUN1=$V1"
echo "VERSIONS_TXT_SHA256_RUN2=$V2"
echo "RELEASE_GATE_LOG_SHA256_RUN1=$L1"
echo "RELEASE_GATE_LOG_SHA256_RUN2=$L2"
echo "PASS: auxiliary output files deterministic across two runs"

