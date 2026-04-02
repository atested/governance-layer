#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
TRIAGE="$ROOT/scripts/triage-eval.py"
VERIFY="$ROOT/scripts/verify-record.py"
FIXTURES="$ROOT/tests/fixtures"
LOG_DIR="$ROOT/LOGS"
RUNTIME_DIR="$ROOT/out/rdd"
TEST_KEY_FILE="$ROOT/system/tests/fixtures/keys/ed25519_test_private.pem"

pass=0
fail=0

pass_case () {
  local id="$1" msg="$2"
  echo "PASS: $id $msg"
  pass=$((pass+1))
}

fail_case () {
  local id="$1" msg="$2"
  echo "FAIL: $id $msg"
  fail=$((fail+1))
}

json_get () {
  local file="$1" path="$2"
  python3 - <<'PY' "$file" "$path"
import json, sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
cur = obj
for part in sys.argv[2].split('.'):
    if part.isdigit():
        cur = cur[int(part)]
    else:
        cur = cur.get(part)
print(json.dumps(cur) if isinstance(cur, (dict, list)) else str(cur))
PY
}

mk_signing_pair () {
  local key_path="$1" pub_path="$2"
  cp "$TEST_KEY_FILE" "$key_path"
  python3 <<PY
from pathlib import Path
from cryptography.hazmat.primitives import serialization
key = Path("$key_path")
priv = serialization.load_pem_private_key(key.read_bytes(), password=None)
pub = priv.public_key()
Path("$pub_path").write_bytes(pub.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
))
PY
}

mkdir -p "$LOG_DIR" "$RUNTIME_DIR"
export GOV_CANONICAL_REPO_PATH="$ROOT"
export GOV_RUNTIME_PATH="$ROOT/out/runtime"

SRC_PATH="$RUNTIME_DIR/phase7-selector-src.txt"
DST_EXISTS_PATH="$RUNTIME_DIR/phase7-selector-dst-exists.txt"
printf 'selector-src\n' > "$SRC_PATH"
printf 'selector-existing\n' > "$DST_EXISTS_PATH"

TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/rdd-triage-selector-test.XXXXXX")"
cleanup() { rm -rf "$TMPDIR_LOCAL"; }
trap cleanup EXIT

KEY_PATH="$TMPDIR_LOCAL/key.pem"
PUB_PATH="$TMPDIR_LOCAL/key.pub.pem"
mk_signing_pair "$KEY_PATH" "$PUB_PATH"
export GOV_SIGNING_KEY_PATH="$KEY_PATH"
export GOV_VERIFY_KEY_PATH="$PUB_PATH"

PASS_UNDECIDED="$TMPDIR_LOCAL/pass-undecided.record.json"
python3 "$EVAL" "$FIXTURES/rdd_triage_pass_undecided_input.json" > "$PASS_UNDECIDED"

OUT_OK="$TMPDIR_LOCAL/selector-ok.record.json"
ERR_OK="$TMPDIR_LOCAL/selector-ok.stderr.txt"
CHAIN_OK="$TMPDIR_LOCAL/selector-ok.chain.jsonl"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase7_triage_criteria_selector_valid.json" \
GOV_DECISION_CHAIN_PATH="$CHAIN_OK" \
python3 "$TRIAGE" "$PASS_UNDECIDED" >"$OUT_OK" 2>"$ERR_OK"
rc_ok="$?"
set -e

[[ "$rc_ok" -eq 0 ]] \
  && pass_case "T-RDD-TRIAGE-SEL-001" "supported selector succeeds" \
  || fail_case "T-RDD-TRIAGE-SEL-001" "supported selector returned non-zero ($rc_ok)"

[[ "$(json_get "$OUT_OK" "governing_condition")" == "F1" ]] \
  && pass_case "T-RDD-TRIAGE-SEL-002" "governing_condition preserved" \
  || fail_case "T-RDD-TRIAGE-SEL-002" "unexpected governing_condition"

python3 "$VERIFY" "$OUT_OK" >/dev/null \
  && pass_case "T-RDD-TRIAGE-SEL-003" "verify-record passes on selected criteria output" \
  || fail_case "T-RDD-TRIAGE-SEL-003" "verify-record failed on selected criteria output"

PASS_UNSUPPORTED="$TMPDIR_LOCAL/pass-unsupported.record.json"
python3 - <<'PY' "$PASS_UNDECIDED" "$PASS_UNSUPPORTED"
import json, pathlib, sys
obj = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
obj["insufficiency"]["trigger"] = "unsupported_trigger"
pathlib.Path(sys.argv[2]).write_text(json.dumps(obj), encoding="utf-8")
PY

ERR_UNSUPPORTED="$TMPDIR_LOCAL/selector-unsupported.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase7_triage_criteria_selector_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/selector-unsupported.chain.jsonl" \
python3 "$TRIAGE" "$PASS_UNSUPPORTED" >/dev/null 2>"$ERR_UNSUPPORTED"
rc_unsupported="$?"
set -e

[[ "$rc_unsupported" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-SEL-004" "unsupported selector fails closed" \
  || fail_case "T-RDD-TRIAGE-SEL-004" "unsupported selector unexpectedly succeeded"

grep -q "TRIAGE_CRITERIA_SELECTOR_UNSUPPORTED" "$ERR_UNSUPPORTED" \
  && pass_case "T-RDD-TRIAGE-SEL-005" "unsupported selector reason marker present" \
  || fail_case "T-RDD-TRIAGE-SEL-005" "unsupported selector reason marker absent"

ERR_MISSING_TARGET="$TMPDIR_LOCAL/selector-missing-target.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase7_triage_criteria_selector_missing_target.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/selector-missing-target.chain.jsonl" \
python3 "$TRIAGE" "$PASS_UNDECIDED" >/dev/null 2>"$ERR_MISSING_TARGET"
rc_missing_target="$?"
set -e

[[ "$rc_missing_target" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-SEL-006" "missing selector target fails closed" \
  || fail_case "T-RDD-TRIAGE-SEL-006" "missing selector target unexpectedly succeeded"

grep -q "TRIAGE_CRITERIA_SELECTOR_TARGET_MISSING" "$ERR_MISSING_TARGET" \
  && pass_case "T-RDD-TRIAGE-SEL-007" "missing selector target reason marker present" \
  || fail_case "T-RDD-TRIAGE-SEL-007" "missing selector target reason marker absent"

ERR_INPUT_INVALID="$TMPDIR_LOCAL/selector-input-invalid.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase7_triage_criteria_selector_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/selector-input-invalid.chain.jsonl" \
python3 "$TRIAGE" "$FIXTURES/rdd_phase7_triage_criteria_selector_malformed_pass.json" >/dev/null 2>"$ERR_INPUT_INVALID"
rc_input_invalid="$?"
set -e

[[ "$rc_input_invalid" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-SEL-008" "malformed selector input fails closed" \
  || fail_case "T-RDD-TRIAGE-SEL-008" "malformed selector input unexpectedly succeeded"

grep -q "TRIAGE_CRITERIA_SELECTOR_INPUT_INVALID" "$ERR_INPUT_INVALID" \
  && pass_case "T-RDD-TRIAGE-SEL-009" "malformed selector input reason marker present" \
  || fail_case "T-RDD-TRIAGE-SEL-009" "malformed selector input reason marker absent"

ERR_MAP_REQUIRED="$TMPDIR_LOCAL/selector-map-required.stderr.txt"
set +e
GOV_TRIAGE_SELECTOR_MODE="explicit" \
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase8_triage_selector_contract_missing_map.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/selector-map-required.chain.jsonl" \
python3 "$TRIAGE" "$PASS_UNDECIDED" >/dev/null 2>"$ERR_MAP_REQUIRED"
rc_map_required="$?"
set -e

[[ "$rc_map_required" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-SEL-010" "explicit mode requires selector_map (fail closed)" \
  || fail_case "T-RDD-TRIAGE-SEL-010" "explicit mode unexpectedly accepted missing selector_map"

grep -q "TRIAGE_CRITERIA_SELECTOR_MAP_REQUIRED" "$ERR_MAP_REQUIRED" \
  && pass_case "T-RDD-TRIAGE-SEL-011" "selector_map required marker present" \
  || fail_case "T-RDD-TRIAGE-SEL-011" "selector_map required marker absent"

ERR_MAP_WRONG_TYPE="$TMPDIR_LOCAL/selector-map-wrong-type.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase8_triage_selector_contract_map_wrong_type.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/selector-map-wrong-type.chain.jsonl" \
python3 "$TRIAGE" "$PASS_UNDECIDED" >/dev/null 2>"$ERR_MAP_WRONG_TYPE"
rc_map_wrong_type="$?"
set -e

[[ "$rc_map_wrong_type" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-SEL-012" "selector_map wrong-type fails closed" \
  || fail_case "T-RDD-TRIAGE-SEL-012" "selector_map wrong-type unexpectedly succeeded"

grep -q "TRIAGE_CRITERIA_SELECTOR_MAP_INVALID expected=object" "$ERR_MAP_WRONG_TYPE" \
  && pass_case "T-RDD-TRIAGE-SEL-013" "selector_map wrong-type marker present" \
  || fail_case "T-RDD-TRIAGE-SEL-013" "selector_map wrong-type marker absent"

ERR_MAP_NON_STRING="$TMPDIR_LOCAL/selector-map-non-string.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase8_triage_selector_contract_map_non_string_entry.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/selector-map-non-string.chain.jsonl" \
python3 "$TRIAGE" "$PASS_UNDECIDED" >/dev/null 2>"$ERR_MAP_NON_STRING"
rc_map_non_string="$?"
set -e

[[ "$rc_map_non_string" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-SEL-014" "selector_map non-string entry fails closed" \
  || fail_case "T-RDD-TRIAGE-SEL-014" "selector_map non-string entry unexpectedly succeeded"

grep -q "TRIAGE_CRITERIA_SELECTOR_MAP_INVALID non_string_entry=present" "$ERR_MAP_NON_STRING" \
  && pass_case "T-RDD-TRIAGE-SEL-015" "selector_map non-string marker present" \
  || fail_case "T-RDD-TRIAGE-SEL-015" "selector_map non-string marker absent"

# Determinism matrix hash (run1).
HASH_1="$(python3 - <<'PY' "$OUT_OK" "$ERR_UNSUPPORTED" "$ERR_MISSING_TARGET" "$ERR_INPUT_INVALID" "$ERR_MAP_REQUIRED" "$ERR_MAP_WRONG_TYPE" "$ERR_MAP_NON_STRING"
import hashlib, json, sys
ok = json.load(open(sys.argv[1], encoding="utf-8"))
for k in ("timestamp_utc","session_id","request_id","process_id","prev_record_hash","record_hash","signature","signing_key_id","request_bytes_b64"):
    ok.pop(k, None)
payload = {
    "ok_normalized": ok,
    "unsupported_marker": open(sys.argv[2], encoding="utf-8").read().strip(),
    "missing_target_marker": open(sys.argv[3], encoding="utf-8").read().strip(),
    "input_invalid_marker": open(sys.argv[4], encoding="utf-8").read().strip(),
    "map_required_marker": open(sys.argv[5], encoding="utf-8").read().strip(),
    "map_wrong_type_marker": open(sys.argv[6], encoding="utf-8").read().strip(),
    "map_non_string_marker": open(sys.argv[7], encoding="utf-8").read().strip(),
}
print(hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest())
PY
)"

# Determinism matrix hash (run2).
OUT_OK_2="$TMPDIR_LOCAL/selector-ok-2.record.json"
ERR_OK_2="$TMPDIR_LOCAL/selector-ok-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase7_triage_criteria_selector_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/selector-ok-2.chain.jsonl" \
python3 "$TRIAGE" "$PASS_UNDECIDED" >"$OUT_OK_2" 2>"$ERR_OK_2"
rc_ok_2="$?"
set -e
[[ "$rc_ok_2" -eq 0 ]] || fail_case "T-RDD-TRIAGE-SEL-016" "run2 supported selector failed ($rc_ok_2)"

ERR_UNSUPPORTED_2="$TMPDIR_LOCAL/selector-unsupported-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase7_triage_criteria_selector_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/selector-unsupported-2.chain.jsonl" \
python3 "$TRIAGE" "$PASS_UNSUPPORTED" >/dev/null 2>"$ERR_UNSUPPORTED_2"
set -e

ERR_MISSING_TARGET_2="$TMPDIR_LOCAL/selector-missing-target-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase7_triage_criteria_selector_missing_target.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/selector-missing-target-2.chain.jsonl" \
python3 "$TRIAGE" "$PASS_UNDECIDED" >/dev/null 2>"$ERR_MISSING_TARGET_2"
set -e

ERR_INPUT_INVALID_2="$TMPDIR_LOCAL/selector-input-invalid-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase7_triage_criteria_selector_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/selector-input-invalid-2.chain.jsonl" \
python3 "$TRIAGE" "$FIXTURES/rdd_phase7_triage_criteria_selector_malformed_pass.json" >/dev/null 2>"$ERR_INPUT_INVALID_2"
set -e

ERR_MAP_REQUIRED_2="$TMPDIR_LOCAL/selector-map-required-2.stderr.txt"
set +e
GOV_TRIAGE_SELECTOR_MODE="explicit" \
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase8_triage_selector_contract_missing_map.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/selector-map-required-2.chain.jsonl" \
python3 "$TRIAGE" "$PASS_UNDECIDED" >/dev/null 2>"$ERR_MAP_REQUIRED_2"
set -e

ERR_MAP_WRONG_TYPE_2="$TMPDIR_LOCAL/selector-map-wrong-type-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase8_triage_selector_contract_map_wrong_type.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/selector-map-wrong-type-2.chain.jsonl" \
python3 "$TRIAGE" "$PASS_UNDECIDED" >/dev/null 2>"$ERR_MAP_WRONG_TYPE_2"
set -e

ERR_MAP_NON_STRING_2="$TMPDIR_LOCAL/selector-map-non-string-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase8_triage_selector_contract_map_non_string_entry.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/selector-map-non-string-2.chain.jsonl" \
python3 "$TRIAGE" "$PASS_UNDECIDED" >/dev/null 2>"$ERR_MAP_NON_STRING_2"
set -e

HASH_2="$(python3 - <<'PY' "$OUT_OK_2" "$ERR_UNSUPPORTED_2" "$ERR_MISSING_TARGET_2" "$ERR_INPUT_INVALID_2" "$ERR_MAP_REQUIRED_2" "$ERR_MAP_WRONG_TYPE_2" "$ERR_MAP_NON_STRING_2"
import hashlib, json, sys
ok = json.load(open(sys.argv[1], encoding="utf-8"))
for k in ("timestamp_utc","session_id","request_id","process_id","prev_record_hash","record_hash","signature","signing_key_id","request_bytes_b64"):
    ok.pop(k, None)
payload = {
    "ok_normalized": ok,
    "unsupported_marker": open(sys.argv[2], encoding="utf-8").read().strip(),
    "missing_target_marker": open(sys.argv[3], encoding="utf-8").read().strip(),
    "input_invalid_marker": open(sys.argv[4], encoding="utf-8").read().strip(),
    "map_required_marker": open(sys.argv[5], encoding="utf-8").read().strip(),
    "map_wrong_type_marker": open(sys.argv[6], encoding="utf-8").read().strip(),
    "map_non_string_marker": open(sys.argv[7], encoding="utf-8").read().strip(),
}
print(hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest())
PY
)"

echo "SELECTOR_MATRIX_HASH_1=$HASH_1"
echo "SELECTOR_MATRIX_HASH_2=$HASH_2"
[[ "$HASH_1" == "$HASH_2" ]] \
  && pass_case "T-RDD-TRIAGE-SEL-017" "selector matrix deterministic hash match" \
  || fail_case "T-RDD-TRIAGE-SEL-017" "selector matrix deterministic hash mismatch"

echo "PASS: $pass  FAIL: $fail"
if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
