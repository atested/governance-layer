#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS_TRIAGE="$ROOT/scripts/rdd-pass-triage.sh"
TERMINAL="$ROOT/scripts/terminal-judgment-eval.py"
VERIFY_RECORD="$ROOT/scripts/verify-record.py"
VERIFY_CHAIN="$ROOT/scripts/verify-chain.py"
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

# Filesystem state: src must exist, category6 dst must NOT exist
SRC_PATH="$RUNTIME_DIR/triage-src.txt"
CAT6_DST_PATH="$RUNTIME_DIR/category6-dst-new.txt"
printf 'triage-src\n' > "$SRC_PATH"
rm -f "$CAT6_DST_PATH"

TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/rdd-terminal-test.XXXXXX")"
cleanup() { rm -rf "$TMPDIR_LOCAL"; }
trap cleanup EXIT
KEY_PATH="$TMPDIR_LOCAL/key.pem"
PUB_PATH="$TMPDIR_LOCAL/key.pub.pem"
mk_signing_pair "$KEY_PATH" "$PUB_PATH"

export GOV_SIGNING_KEY_PATH="$KEY_PATH"
export GOV_VERIFY_KEY_PATH="$PUB_PATH"

# ============================================================
# Test 1-6: Full pass → triage → terminal judgment chain
# ============================================================

CHAIN="$TMPDIR_LOCAL/rdd-terminal.chain.jsonl"
OUT_TRIAGE="$TMPDIR_LOCAL/triage-cat6.record.json"

# Run pass → triage for Category 6 input
GOV_DECISION_CHAIN_PATH="$CHAIN" "$PASS_TRIAGE" "$FIXTURES/rdd_category6_authorization_required_input.json" > "$OUT_TRIAGE"

# T-RDD-TJ-001: triage record is triage_decision
[[ "$(json_get "$OUT_TRIAGE" "record_type")" == "triage_decision" ]] \
  && pass_case "T-RDD-TJ-001" "record_type triage_decision" \
  || fail_case "T-RDD-TJ-001" "expected triage_decision"

# T-RDD-TJ-002: disposition is ESCALATION_JUSTIFIED (Category 6)
[[ "$(json_get "$OUT_TRIAGE" "disposition.type")" == "ESCALATION_JUSTIFIED" ]] \
  && pass_case "T-RDD-TJ-002" "disposition type ESCALATION_JUSTIFIED" \
  || fail_case "T-RDD-TJ-002" "unexpected disposition type"

# T-RDD-TJ-003: finding is genuine_residual
[[ "$(json_get "$OUT_TRIAGE" "findings.0.type")" == "genuine_residual" ]] \
  && pass_case "T-RDD-TJ-003" "finding type genuine_residual" \
  || fail_case "T-RDD-TJ-003" "unexpected finding type"

# Now run terminal judgment
OUT_TERMINAL="$TMPDIR_LOCAL/terminal.record.json"
GOV_DECISION_CHAIN_PATH="$CHAIN" python3 "$TERMINAL" "$OUT_TRIAGE" \
  --method human_authority \
  --outcome ALLOW \
  --decider-identity "product_owner:test" \
  --decider-authority "authorization_grant" \
  --rationale "Test authorization granted by product owner." \
  > "$OUT_TERMINAL"

# T-RDD-TJ-004: terminal record is terminal_judgment
[[ "$(json_get "$OUT_TERMINAL" "record_type")" == "terminal_judgment" ]] \
  && pass_case "T-RDD-TJ-004" "record_type terminal_judgment" \
  || fail_case "T-RDD-TJ-004" "expected terminal_judgment"

# T-RDD-TJ-005: outcome is ALLOW
[[ "$(json_get "$OUT_TERMINAL" "outcome")" == "ALLOW" ]] \
  && pass_case "T-RDD-TJ-005" "outcome ALLOW" \
  || fail_case "T-RDD-TJ-005" "unexpected outcome"

# T-RDD-TJ-006: policy_decision bridges outcome (ALLOW)
[[ "$(json_get "$OUT_TERMINAL" "policy_decision")" == "ALLOW" ]] \
  && pass_case "T-RDD-TJ-006" "policy_decision bridges outcome" \
  || fail_case "T-RDD-TJ-006" "policy_decision does not bridge outcome"

# T-RDD-TJ-007: originating_triage_hash matches triage record_hash
TRIAGE_HASH="$(json_get "$OUT_TRIAGE" "record_hash")"
TERMINAL_ORIG="$(json_get "$OUT_TERMINAL" "originating_triage_hash")"
[[ "$TERMINAL_ORIG" == "$TRIAGE_HASH" ]] \
  && pass_case "T-RDD-TJ-007" "originating_triage_hash linkage" \
  || fail_case "T-RDD-TJ-007" "originating_triage_hash mismatch"

# T-RDD-TJ-008: verify-record passes for terminal output
python3 "$VERIFY_RECORD" "$OUT_TERMINAL" >/dev/null \
  && pass_case "T-RDD-TJ-008" "verify-record passes for terminal output" \
  || fail_case "T-RDD-TJ-008" "verify-record failed for terminal output"

# ============================================================
# Test 9: 3-record chain verification
# ============================================================

python3 "$VERIFY_CHAIN" "$CHAIN" >/dev/null 2>&1 \
  && pass_case "T-RDD-TJ-009" "3-record chain verified by verify-chain.py" \
  || fail_case "T-RDD-TJ-009" "3-record chain verification failed"

SUMMARY_JSON="$TMPDIR_LOCAL/chain_summary.json"
python3 "$VERIFY_CHAIN" --summary-json "$SUMMARY_JSON" "$CHAIN" >/dev/null 2>&1 \
  || fail_case "T-RDD-TJ-009A" "summary-json emission failed"
python3 - <<'PY' "$SUMMARY_JSON" "$TRIAGE_HASH"
import json, sys
raw = open(sys.argv[1], encoding="utf-8").read()
assert raw.endswith("\n")
obj = json.loads(raw)
assert obj["report_version"] == "chain_verification_summary_v1"
assert obj["result"] == "PASS"
assert obj["counts"]["records_total"] == 3
assert obj["counts"]["terminal_judgment"] == 1
assert obj["rdd_terminal_process_summary"]["completed_rdd_process_count"] == 1
assert obj["rdd_terminal_process_summary"]["allow_terminal_process_count"] == 1
row = obj["rdd_terminal_process_summary"]["completed_rdd_processes"][0]
assert row["terminal_outcome"] == "ALLOW"
assert row["triage_disposition_type"] == "ESCALATION_JUSTIFIED"
print("PASS: summary-json captures completed RDD terminal chain")
PY
if [[ "$?" -eq 0 ]]; then
  pass_case "T-RDD-TJ-009A" "summary-json captures completed RDD terminal chain"
else
  fail_case "T-RDD-TJ-009A" "summary-json missing expected fields"
fi

# Validate chain structure: pass → triage → terminal with correct linkage
python3 - <<'PY' "$CHAIN" >/dev/null
import json, sys, pathlib
chain = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").strip().splitlines()
if len(chain) != 3:
    print(f"expected 3 records, got {len(chain)}", file=sys.stderr)
    raise SystemExit(1)
first = json.loads(chain[0])
second = json.loads(chain[1])
third = json.loads(chain[2])
if first.get("record_type") != "pass_decision":
    raise SystemExit(1)
if second.get("record_type") != "triage_decision":
    raise SystemExit(1)
if third.get("record_type") != "terminal_judgment":
    raise SystemExit(1)
if second.get("prev_record_hash") != first.get("record_hash"):
    raise SystemExit(1)
if third.get("prev_record_hash") != second.get("record_hash"):
    raise SystemExit(1)
PY
if [[ "$?" -eq 0 ]]; then
  pass_case "T-RDD-TJ-010" "chain structure pass→triage→terminal with linkage"
else
  fail_case "T-RDD-TJ-010" "chain structure invalid"
fi

# ============================================================
# Test 11-12: Fail-closed cases
# ============================================================

# T-RDD-TJ-011: wrong method for disposition (bounded_estimation instead of human_authority)
set +e
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/fc1.chain.jsonl" python3 "$TERMINAL" "$OUT_TRIAGE" \
  --method bounded_estimation \
  --outcome ALLOW \
  --decider-identity "product_owner:test" \
  --decider-authority "authorization_grant" \
  --rationale "Should fail: wrong method." \
  >/dev/null 2>&1
rc_wrong_method="$?"
set -e
[[ "$rc_wrong_method" -ne 0 ]] \
  && pass_case "T-RDD-TJ-011" "fail-closed on wrong method for disposition" \
  || fail_case "T-RDD-TJ-011" "expected non-zero for wrong method"

# T-RDD-TJ-012: non_resolution method with ALLOW outcome (constraint violation)
set +e
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/fc2.chain.jsonl" python3 "$TERMINAL" "$OUT_TRIAGE" \
  --method non_resolution \
  --outcome ALLOW \
  --decider-identity "product_owner:test" \
  --decider-authority "authorization_grant" \
  --rationale "Should fail: non_resolution cannot produce ALLOW." \
  >/dev/null 2>&1
rc_bad_outcome="$?"
set -e
[[ "$rc_bad_outcome" -ne 0 ]] \
  && pass_case "T-RDD-TJ-012" "fail-closed on non_resolution with ALLOW" \
  || fail_case "T-RDD-TJ-012" "expected non-zero for invalid outcome"

# T-RDD-TJ-013: empty rationale
set +e
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/fc3.chain.jsonl" python3 "$TERMINAL" "$OUT_TRIAGE" \
  --method human_authority \
  --outcome ALLOW \
  --decider-identity "product_owner:test" \
  --decider-authority "authorization_grant" \
  --rationale "   " \
  >/dev/null 2>&1
rc_empty_rationale="$?"
set -e
[[ "$rc_empty_rationale" -ne 0 ]] \
  && pass_case "T-RDD-TJ-013" "fail-closed on empty rationale" \
  || fail_case "T-RDD-TJ-013" "expected non-zero for empty rationale"

# ============================================================
# Summary
# ============================================================

echo "PASS: $pass  FAIL: $fail"
if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
