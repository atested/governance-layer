#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS_TRIAGE="$ROOT/scripts/rdd-pass-triage.sh"
TRIAGE="$ROOT/scripts/triage-eval.py"
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

SRC_PATH="$RUNTIME_DIR/triage-src.txt"
DST_EXISTS_PATH="$RUNTIME_DIR/triage-dst-exists.txt"
DST_NEW_PATH="$RUNTIME_DIR/triage-dst-new.txt"
printf 'triage-src\n' > "$SRC_PATH"
printf 'triage-existing\n' > "$DST_EXISTS_PATH"
rm -f "$DST_NEW_PATH"

TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/rdd-triage-test.XXXXXX")"
cleanup() { rm -rf "$TMPDIR_LOCAL"; }
trap cleanup EXIT
KEY_PATH="$TMPDIR_LOCAL/key.pem"
PUB_PATH="$TMPDIR_LOCAL/key.pub.pem"
mk_signing_pair "$KEY_PATH" "$PUB_PATH"

export GOV_SIGNING_KEY_PATH="$KEY_PATH"
export GOV_VERIFY_KEY_PATH="$PUB_PATH"

CHAIN="$TMPDIR_LOCAL/rdd-triage.chain.jsonl"
OUT_UNDECIDED="$TMPDIR_LOCAL/triage-undecided.record.json"
GOV_DECISION_CHAIN_PATH="$CHAIN" "$PASS_TRIAGE" "$FIXTURES/rdd_triage_pass_undecided_input.json" > "$OUT_UNDECIDED"

[[ "$(json_get "$OUT_UNDECIDED" "record_type")" == "triage_decision" ]] \
  && pass_case "T-RDD-TRIAGE-001" "record_type triage_decision" \
  || fail_case "T-RDD-TRIAGE-001" "expected triage_decision"

[[ "$(json_get "$OUT_UNDECIDED" "governing_condition")" == "F1" ]] \
  && pass_case "T-RDD-TRIAGE-002" "governing_condition F1" \
  || fail_case "T-RDD-TRIAGE-002" "unexpected governing_condition"

[[ "$(json_get "$OUT_UNDECIDED" "disposition.type")" == "DEFER_STRUCTURAL_DEFICIENCY" ]] \
  && pass_case "T-RDD-TRIAGE-003" "disposition type" \
  || fail_case "T-RDD-TRIAGE-003" "unexpected disposition type"

[[ "$(json_get "$OUT_UNDECIDED" "findings.0.id")" == "F1" && "$(json_get "$OUT_UNDECIDED" "findings.1.id")" == "F2" ]] \
  && pass_case "T-RDD-TRIAGE-004" "findings include F1/F2" \
  || fail_case "T-RDD-TRIAGE-004" "findings missing F1/F2"

[[ "$(json_get "$OUT_UNDECIDED" "originating_pass_hash")" == "$(json_get "$OUT_UNDECIDED" "prev_record_hash")" ]] \
  && pass_case "T-RDD-TRIAGE-005" "originating hash linked to prev_record_hash" \
  || fail_case "T-RDD-TRIAGE-005" "originating/prev linkage mismatch"

python3 "$VERIFY" "$OUT_UNDECIDED" >/dev/null \
  && pass_case "T-RDD-TRIAGE-006" "verify-record passes for triage output" \
  || fail_case "T-RDD-TRIAGE-006" "verify-record failed for triage output"

python3 - <<'PY' "$CHAIN" >/dev/null
import json, sys, pathlib
chain = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").strip().splitlines()
if len(chain) != 2:
    raise SystemExit(1)
first = json.loads(chain[0])
second = json.loads(chain[1])
if first.get("record_type") != "pass_decision":
    raise SystemExit(1)
if second.get("record_type") != "triage_decision":
    raise SystemExit(1)
if second.get("prev_record_hash") != first.get("record_hash"):
    raise SystemExit(1)
PY
if [[ "$?" -eq 0 ]]; then
  pass_case "T-RDD-TRIAGE-007" "chain append and linkage validated"
else
  fail_case "T-RDD-TRIAGE-007" "chain linkage invalid"
fi

CHAIN_ALLOW="$TMPDIR_LOCAL/rdd-triage-allow.chain.jsonl"
OUT_ALLOW="$TMPDIR_LOCAL/pass-allow.record.json"
GOV_DECISION_CHAIN_PATH="$CHAIN_ALLOW" "$PASS_TRIAGE" "$FIXTURES/rdd_triage_pass_allow_input.json" > "$OUT_ALLOW"

[[ "$(json_get "$OUT_ALLOW" "record_type")" == "pass_decision" && "$(json_get "$OUT_ALLOW" "policy_decision")" == "ALLOW" ]] \
  && pass_case "T-RDD-TRIAGE-008" "non-undecided skips triage" \
  || fail_case "T-RDD-TRIAGE-008" "expected pass ALLOW output"

python3 - <<'PY' "$OUT_ALLOW" "$TMPDIR_LOCAL/invalid-pass.json"
import json, pathlib, sys
rec = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
rec["policy_decision"] = "ALLOW"
pathlib.Path(sys.argv[2]).write_text(json.dumps(rec), encoding="utf-8")
PY
set +e
python3 "$TRIAGE" "$TMPDIR_LOCAL/invalid-pass.json" >/dev/null 2>&1
rc_invalid="$?"
set -e
[[ "$rc_invalid" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-009" "triage fails closed on non-UNDECIDED input" \
  || fail_case "T-RDD-TRIAGE-009" "expected non-zero for invalid triage input"

# Determinism check on triage semantic projection.
CHAIN_D1="$TMPDIR_LOCAL/rdd-triage-det1.chain.jsonl"
CHAIN_D2="$TMPDIR_LOCAL/rdd-triage-det2.chain.jsonl"
OUT_D1="$TMPDIR_LOCAL/triage-det1.record.json"
OUT_D2="$TMPDIR_LOCAL/triage-det2.record.json"
GOV_DECISION_CHAIN_PATH="$CHAIN_D1" "$PASS_TRIAGE" "$FIXTURES/rdd_triage_pass_undecided_input.json" > "$OUT_D1"
GOV_DECISION_CHAIN_PATH="$CHAIN_D2" "$PASS_TRIAGE" "$FIXTURES/rdd_triage_pass_undecided_input.json" > "$OUT_D2"

DET_HASH_1="$(python3 - <<'PY' "$OUT_D1"
import hashlib, json, sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
for k in ("timestamp_utc","session_id","request_id","process_id","prev_record_hash","record_hash","signature","signing_key_id","request_bytes_b64"):
    obj.pop(k, None)
print(hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode("utf-8")).hexdigest())
PY
)"
DET_HASH_2="$(python3 - <<'PY' "$OUT_D2"
import hashlib, json, sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
for k in ("timestamp_utc","session_id","request_id","process_id","prev_record_hash","record_hash","signature","signing_key_id","request_bytes_b64"):
    obj.pop(k, None)
print(hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode("utf-8")).hexdigest())
PY
)"
[[ "$DET_HASH_1" == "$DET_HASH_2" ]] \
  && pass_case "T-RDD-TRIAGE-010" "deterministic normalized triage output" \
  || fail_case "T-RDD-TRIAGE-010" "normalized triage output hash mismatch"
echo "DET_HASH_1=$DET_HASH_1"
echo "DET_HASH_2=$DET_HASH_2"

echo "PASS: $pass  FAIL: $fail"
if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
