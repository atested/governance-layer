#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task179-optional-neg.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

sha256_normalized() {
  python3 - <<'PY' "$1"
import hashlib, pathlib, re, sys
txt = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
txt = re.sub(r"^BUNDLE_DIR=.*$", "BUNDLE_DIR=<normalized>", txt, flags=re.M)
txt = re.sub(r"/tmp/task179-optional-neg\\.[A-Za-z0-9]+", "/tmp/task179-optional-neg.NORMALIZED", txt)
print(hashlib.sha256(txt.encode("utf-8")).hexdigest())
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
  [[ "$rc1" -eq "$expected_rc" && "$rc2" -eq "$expected_rc" ]] || { echo "FAIL: ${label} rc mismatch"; exit 1; }
  rg -q "$marker" "$out1" || { echo "FAIL: ${label} marker missing run1"; exit 1; }
  rg -q "$marker" "$out2" || { echo "FAIL: ${label} marker missing run2"; exit 1; }
  h1="$(sha256_normalized "$out1")"; h2="$(sha256_normalized "$out2")"
  echo "${label}_SHA256_RUN1=${h1}"
  echo "${label}_SHA256_RUN2=${h2}"
  [[ "$h1" == "$h2" ]] || { echo "FAIL: ${label} nondeterministic"; exit 1; }
  echo "PASS: ${label} deterministic output"
}

BASE_OUT="$TMPDIR_LOCAL/out/proof-bundles"
RELEASE_GATE_SKIP_BASE=1 GOV_PROFILE=dev RELEASE_GATE_RUN_ID="task179" RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$BASE_OUT" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/release_gate.out"
VALID_DIR="$BASE_OUT/task179"

echo "--- T-VALIDATE-OPT-001: valid optional files present passes deterministically ---"
run_case_twice "OPT_PRESENT_VALID" "$VALID_DIR" 0 "PASS: proof-bundle external contract valid"

echo "--- T-VALIDATE-OPT-002: qds json linkage mismatch fails deterministically ---"
BAD_QDS="$TMPDIR_LOCAL/bad-qds"
cp -R "$VALID_DIR" "$BAD_QDS"
python3 - <<'PY' "$BAD_QDS/queue_drift_scan.json"
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
j = json.loads(p.read_text(encoding="utf-8"))
j["text_sha256"] = "f" * 64
p.write_text(json.dumps(j, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
run_case_twice "OPT_QDS_BAD_LINK" "$BAD_QDS" 1 "FAIL: queue_drift_scan.json text_sha256 linkage mismatch"

echo "--- T-VALIDATE-OPT-003: status bundle strictness type mismatch fails deterministically ---"
BAD_STATUS="$TMPDIR_LOCAL/bad-status"
cp -R "$VALID_DIR" "$BAD_STATUS"
python3 - <<'PY' "$BAD_STATUS/status_bundle.json"
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
j = json.loads(p.read_text(encoding="utf-8"))
j.setdefault("strictness", {})["value"] = "1"
p.write_text(json.dumps(j, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
run_case_twice "OPT_STATUS_BAD_TYPE" "$BAD_STATUS" 1 "FAIL: strictness.value not int 0\\|1"

echo "--- T-VALIDATE-OPT-004: optional files absent remain PASS deterministically ---"
ABSENT="$TMPDIR_LOCAL/optional-absent"
cp -R "$VALID_DIR" "$ABSENT"
rm -f "$ABSENT/queue_drift_scan.json" "$ABSENT/status_bundle.json"
run_case_twice "OPT_FILES_ABSENT" "$ABSENT" 0 "INFO: queue_drift_scan.json absent \\(optional\\)"

echo "Summary: validator optional-files negative controls matrix complete"
