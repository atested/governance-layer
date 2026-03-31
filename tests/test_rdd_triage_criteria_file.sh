#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS_TRIAGE="$ROOT/scripts/rdd-pass-triage.sh"
VERIFY="$ROOT/scripts/verify-record.py"
FIXTURES="$ROOT/tests/fixtures"
LOG_DIR="$ROOT/LOGS"
RUNTIME_DIR="$ROOT/out/rdd"

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
  cat > "$key_path" <<'PEM'
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIKY6z3CMVvjJkqQW3AX6mEGoVYLRsKcJsteU8h1Hn0pG
-----END PRIVATE KEY-----
PEM
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

TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/rdd-triage-criteria-test.XXXXXX")"
cleanup() { rm -rf "$TMPDIR_LOCAL"; }
trap cleanup EXIT

KEY_PATH="$TMPDIR_LOCAL/key.pem"
PUB_PATH="$TMPDIR_LOCAL/key.pub.pem"
mk_signing_pair "$KEY_PATH" "$PUB_PATH"
export GOV_SIGNING_KEY_PATH="$KEY_PATH"
export GOV_VERIFY_KEY_PATH="$PUB_PATH"

CHAIN_OK="$TMPDIR_LOCAL/criteria-ok.chain.jsonl"
OUT_OK="$TMPDIR_LOCAL/criteria-ok.record.json"
ERR_OK="$TMPDIR_LOCAL/criteria-ok.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase6_triage_criteria_valid.json" \
GOV_DECISION_CHAIN_PATH="$CHAIN_OK" \
"$PASS_TRIAGE" "$FIXTURES/rdd_triage_pass_undecided_input.json" >"$OUT_OK" 2>"$ERR_OK"
rc_ok="$?"
set -e

[[ "$rc_ok" -eq 0 ]] \
  && pass_case "T-RDD-TRIAGE-CRIT-001" "valid criteria file executed" \
  || fail_case "T-RDD-TRIAGE-CRIT-001" "valid criteria returned non-zero ($rc_ok)"

[[ "$(json_get "$OUT_OK" "governing_condition")" == "F1" ]] \
  && pass_case "T-RDD-TRIAGE-CRIT-002" "governing_condition preserved" \
  || fail_case "T-RDD-TRIAGE-CRIT-002" "unexpected governing_condition"

[[ "$(json_get "$OUT_OK" "disposition.type")" == "DEFER_STRUCTURAL_DEFICIENCY" ]] \
  && pass_case "T-RDD-TRIAGE-CRIT-003" "disposition type preserved" \
  || fail_case "T-RDD-TRIAGE-CRIT-003" "unexpected disposition type"

python3 "$VERIFY" "$OUT_OK" >/dev/null \
  && pass_case "T-RDD-TRIAGE-CRIT-004" "verify-record passes with external criteria" \
  || fail_case "T-RDD-TRIAGE-CRIT-004" "verify-record failed with external criteria"

OUT_MISSING="$TMPDIR_LOCAL/criteria-missing.record.json"
ERR_MISSING="$TMPDIR_LOCAL/criteria-missing.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$TMPDIR_LOCAL/does-not-exist.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/criteria-missing.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_triage_pass_undecided_input.json" >"$OUT_MISSING" 2>"$ERR_MISSING"
rc_missing="$?"
set -e

[[ "$rc_missing" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-CRIT-005" "missing criteria file fails closed" \
  || fail_case "T-RDD-TRIAGE-CRIT-005" "missing criteria unexpectedly succeeded"

grep -q "TRIAGE_CRITERIA_MISSING_FILE" "$ERR_MISSING" \
  && pass_case "T-RDD-TRIAGE-CRIT-006" "missing-file reason marker present" \
  || fail_case "T-RDD-TRIAGE-CRIT-006" "missing-file reason marker absent"

OUT_MALFORMED="$TMPDIR_LOCAL/criteria-malformed.record.json"
ERR_MALFORMED="$TMPDIR_LOCAL/criteria-malformed.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase6_triage_criteria_malformed.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/criteria-malformed.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_triage_pass_undecided_input.json" >"$OUT_MALFORMED" 2>"$ERR_MALFORMED"
rc_malformed="$?"
set -e

[[ "$rc_malformed" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-CRIT-007" "malformed criteria fails closed" \
  || fail_case "T-RDD-TRIAGE-CRIT-007" "malformed criteria unexpectedly succeeded"

grep -q "TRIAGE_CRITERIA_MALFORMED_JSON" "$ERR_MALFORMED" \
  && pass_case "T-RDD-TRIAGE-CRIT-008" "malformed-json reason marker present" \
  || fail_case "T-RDD-TRIAGE-CRIT-008" "malformed-json reason marker absent"

OUT_SCHEMA="$TMPDIR_LOCAL/criteria-schema.record.json"
ERR_SCHEMA="$TMPDIR_LOCAL/criteria-schema.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase6_triage_criteria_missing_fields.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/criteria-schema.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_triage_pass_undecided_input.json" >"$OUT_SCHEMA" 2>"$ERR_SCHEMA"
rc_schema="$?"
set -e

[[ "$rc_schema" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-CRIT-009" "schema-invalid criteria fails closed" \
  || fail_case "T-RDD-TRIAGE-CRIT-009" "schema-invalid criteria unexpectedly succeeded"

grep -q "TRIAGE_CRITERIA_SCHEMA_INVALID" "$ERR_SCHEMA" \
  && pass_case "T-RDD-TRIAGE-CRIT-010" "schema-invalid reason marker present" \
  || fail_case "T-RDD-TRIAGE-CRIT-010" "schema-invalid reason marker absent"

# Determinism matrix hash check across repeated run set.
HASH_1="$(python3 - <<'PY' "$OUT_OK" "$ERR_MISSING" "$ERR_MALFORMED" "$ERR_SCHEMA"
import hashlib, json, sys
ok = json.load(open(sys.argv[1], encoding="utf-8"))
for k in ("timestamp_utc","session_id","request_id","process_id","prev_record_hash","record_hash","signature","signing_key_id","request_bytes_b64"):
    ok.pop(k, None)
payload = {
    "ok_normalized": ok,
    "missing_marker": open(sys.argv[2], encoding="utf-8").read().strip(),
    "malformed_marker": open(sys.argv[3], encoding="utf-8").read().strip(),
    "schema_marker": open(sys.argv[4], encoding="utf-8").read().strip(),
}
print(hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest())
PY
)"

CHAIN_OK_2="$TMPDIR_LOCAL/criteria-ok-2.chain.jsonl"
OUT_OK_2="$TMPDIR_LOCAL/criteria-ok-2.record.json"
ERR_OK_2="$TMPDIR_LOCAL/criteria-ok-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase6_triage_criteria_valid.json" \
GOV_DECISION_CHAIN_PATH="$CHAIN_OK_2" \
"$PASS_TRIAGE" "$FIXTURES/rdd_triage_pass_undecided_input.json" >"$OUT_OK_2" 2>"$ERR_OK_2"
rc_ok_2="$?"
set -e
[[ "$rc_ok_2" -eq 0 ]] || fail_case "T-RDD-TRIAGE-CRIT-011" "determinism pass #2 valid criteria failed ($rc_ok_2)"

ERR_MISSING_2="$TMPDIR_LOCAL/criteria-missing-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$TMPDIR_LOCAL/does-not-exist.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/criteria-missing-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_triage_pass_undecided_input.json" >/dev/null 2>"$ERR_MISSING_2"
set -e

ERR_MALFORMED_2="$TMPDIR_LOCAL/criteria-malformed-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase6_triage_criteria_malformed.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/criteria-malformed-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_triage_pass_undecided_input.json" >/dev/null 2>"$ERR_MALFORMED_2"
set -e

ERR_SCHEMA_2="$TMPDIR_LOCAL/criteria-schema-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase6_triage_criteria_missing_fields.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/criteria-schema-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_triage_pass_undecided_input.json" >/dev/null 2>"$ERR_SCHEMA_2"
set -e

HASH_2="$(python3 - <<'PY' "$OUT_OK_2" "$ERR_MISSING_2" "$ERR_MALFORMED_2" "$ERR_SCHEMA_2"
import hashlib, json, sys
ok = json.load(open(sys.argv[1], encoding="utf-8"))
for k in ("timestamp_utc","session_id","request_id","process_id","prev_record_hash","record_hash","signature","signing_key_id","request_bytes_b64"):
    ok.pop(k, None)
payload = {
    "ok_normalized": ok,
    "missing_marker": open(sys.argv[2], encoding="utf-8").read().strip(),
    "malformed_marker": open(sys.argv[3], encoding="utf-8").read().strip(),
    "schema_marker": open(sys.argv[4], encoding="utf-8").read().strip(),
}
print(hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest())
PY
)"

echo "MATRIX_HASH_1=$HASH_1"
echo "MATRIX_HASH_2=$HASH_2"
[[ "$HASH_1" == "$HASH_2" ]] \
  && pass_case "T-RDD-TRIAGE-CRIT-012" "criteria matrix deterministic hash match" \
  || fail_case "T-RDD-TRIAGE-CRIT-012" "criteria matrix deterministic hash mismatch"

echo "PASS: $pass  FAIL: $fail"
if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
