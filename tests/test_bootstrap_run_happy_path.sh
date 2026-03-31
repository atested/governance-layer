#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task153-bootstrap-happy.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

assert_required_bundle_files() {
  local bundle_dir="$1"
  local f
  for f in proof_packet.tar proof_packet_verify_summary.json proof_packet.sha256 release_gate_log.txt versions.txt; do
    [[ -f "$bundle_dir/$f" ]] || { echo "FAIL: missing required file: $f"; return 1; }
  done
  echo "PASS: required proof-bundle files present"
}

emit_summary() {
  local bundle_dir="$1"
  local out="$2"
  python3 - <<'PY' "$bundle_dir" > "$out"
import hashlib, json, pathlib, sys
b = pathlib.Path(sys.argv[1])
summary = json.loads((b / "proof_packet_verify_summary.json").read_text())
vals = {
    "packet_sha": hashlib.sha256((b / "proof_packet.tar").read_bytes()).hexdigest(),
    "summary_sha": hashlib.sha256((b / "proof_packet_verify_summary.json").read_bytes()).hexdigest(),
    "proof_packet_sha256_file_sha": hashlib.sha256((b / "proof_packet.sha256").read_bytes()).hexdigest(),
    "release_gate_log_sha": hashlib.sha256((b / "release_gate_log.txt").read_bytes()).hexdigest(),
    "versions_sha": hashlib.sha256((b / "versions.txt").read_bytes()).hexdigest(),
    "report_version": summary.get("report_version"),
}
for k in sorted(vals):
    print(f"{k}={vals[k]}")
PY
}

run_once() {
  local run_id="$1"
  local capture="$2"
  local venv_dir="$3"
  local out_base="$4"
  BOOTSTRAP_VENV_DIR="$venv_dir" \
  BOOTSTRAP_SKIP_INSTALL=1 \
  BOOTSTRAP_RELEASE_GATE_SKIP_BASE=1 \
  RELEASE_GATE_RUN_ID="$run_id" \
  RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$out_base" \
  GOV_PROFILE=dev \
  bash "$ROOT/system/scripts/bootstrap-run.sh" > "$capture"
}

echo "--- T-BOOTSTRAP-HAPPY-001: real bootstrap-run path emits proof bundle and is deterministic ---"
run_once fixed-run "$TMPDIR_LOCAL/run1.out" "$TMPDIR_LOCAL/.venv" "$TMPDIR_LOCAL/out"
BUNDLE_DIR="$TMPDIR_LOCAL/out/fixed-run"
assert_required_bundle_files "$BUNDLE_DIR"
emit_summary "$BUNDLE_DIR" "$TMPDIR_LOCAL/summary1.txt"

run_once fixed-run "$TMPDIR_LOCAL/run2.out" "$TMPDIR_LOCAL/.venv" "$TMPDIR_LOCAL/out"
assert_required_bundle_files "$BUNDLE_DIR"
emit_summary "$BUNDLE_DIR" "$TMPDIR_LOCAL/summary2.txt"

S1="$(sha256_file "$TMPDIR_LOCAL/summary1.txt")"
S2="$(sha256_file "$TMPDIR_LOCAL/summary2.txt")"
[[ "$S1" == "$S2" ]] || { echo "FAIL: bootstrap happy-path summary nondeterministic"; exit 1; }

grep -q 'BOOTSTRAP_EXPECTED_OUTPUT_DIR=out/proof-bundles/<run-id>/' "$TMPDIR_LOCAL/run1.out"
grep -q 'INFO: bootstrap pip install skipped via BOOTSTRAP_SKIP_INSTALL=1' "$TMPDIR_LOCAL/run1.out"

echo "BOOTSTRAP_HAPPY_SHA256_RUN1=$S1"
echo "BOOTSTRAP_HAPPY_SHA256_RUN2=$S2"
echo "PASS: bootstrap-run happy path emits deterministic proof-bundle summary"

