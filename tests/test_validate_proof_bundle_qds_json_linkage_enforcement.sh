#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task183-qds-linkage.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

run_case_twice() {
  local label="$1"; shift
  local bundle_dir="$1"; shift
  local expected_rc="$1"; shift
  local marker="$1"; shift

  local out1="$TMPDIR_LOCAL/${label}.run1.out"
  local out2="$TMPDIR_LOCAL/${label}.run2.out"
  local rc1 rc2 h1 h2

  set +e
  bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$bundle_dir" >"$out1" 2>&1
  rc1=$?
  bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$bundle_dir" >"$out2" 2>&1
  rc2=$?
  set -e

  echo "PASS: ${label} rc run1=${rc1} run2=${rc2}"
  [[ "$rc1" -eq "$expected_rc" && "$rc2" -eq "$expected_rc" ]] || {
    echo "FAIL: ${label} unexpected rc"; exit 1;
  }

  rg -q "$marker" "$out1" || { echo "FAIL: ${label} marker missing run1"; exit 1; }
  rg -q "$marker" "$out2" || { echo "FAIL: ${label} marker missing run2"; exit 1; }

  h1="$(sha256_file "$out1")"
  h2="$(sha256_file "$out2")"
  echo "${label}_SHA256_RUN1=${h1}"
  echo "${label}_SHA256_RUN2=${h2}"
  [[ "$h1" == "$h2" ]] || { echo "FAIL: ${label} nondeterministic output"; exit 1; }
  echo "PASS: ${label} deterministic output"
}

BASE_OUT="$TMPDIR_LOCAL/out/proof-bundles"
RELEASE_GATE_SKIP_BASE=1 GOV_PROFILE=dev RELEASE_GATE_RUN_ID="task183" RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$BASE_OUT" \
  bash "$ROOT/system/scripts/release-gate.sh" >"$TMPDIR_LOCAL/release_gate.out"
VALID_DIR="$BASE_OUT/task183"

echo "--- T-VALIDATE-QDSJSON-001: PASS valid qds json linkage deterministic ---"
run_case_twice "QDSJSON_PASS" "$VALID_DIR" 0 "PASS: queue_drift_scan.json schema/version and text digest linkage valid"

echo "--- T-VALIDATE-QDSJSON-002: FAIL qds json text_sha256 mismatch deterministic ---"
BAD_DIR="$TMPDIR_LOCAL/bad-qds-link"
cp -R "$VALID_DIR" "$BAD_DIR"
python3 - <<'PY' "$BAD_DIR/queue_drift_scan.json"
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
j = json.loads(p.read_text(encoding="utf-8"))
j["text_sha256"] = "0" * 64
p.write_text(json.dumps(j, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
run_case_twice "QDSJSON_BAD_LINK" "$BAD_DIR" 1 "FAIL: queue_drift_scan.json text_sha256 linkage mismatch"

echo "--- T-VALIDATE-QDSJSON-003: optional qds json absent remains PASS deterministic ---"
NOJSON_DIR="$TMPDIR_LOCAL/no-qds-json"
cp -R "$VALID_DIR" "$NOJSON_DIR"
rm -f "$NOJSON_DIR/queue_drift_scan.json"
run_case_twice "QDSJSON_ABSENT_OPTIONAL" "$NOJSON_DIR" 0 "INFO: queue_drift_scan.json absent \\(optional\\)"

echo "Summary: qds json linkage enforcement checks complete"
