#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS_TRIAGE="$ROOT/scripts/rdd-pass-triage.sh"
TERMINAL="$ROOT/scripts/terminal-judgment-eval.py"
VERIFY_CHAIN="$ROOT/scripts/verify-chain.py"
FIXTURES="$ROOT/tests/fixtures"
LOG_DIR="$ROOT/LOGS"
RUNTIME_DIR="$ROOT/out/rdd"
TEST_KEY_FILE="$ROOT/system/tests/fixtures/keys/ed25519_test_private.pem"

mkdir -p "$LOG_DIR" "$RUNTIME_DIR"
export GOV_CANONICAL_REPO_PATH="$ROOT"
export GOV_RUNTIME_PATH="$ROOT/out/runtime"

SRC_PATH="$RUNTIME_DIR/triage-src.txt"
CAT6_DST_PATH="$RUNTIME_DIR/category6-dst-new.txt"
printf 'triage-src\n' > "$SRC_PATH"
rm -f "$CAT6_DST_PATH"

TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/verify-chain-summary.XXXXXX")"
cleanup() { rm -rf "$TMPDIR_LOCAL"; }
trap cleanup EXIT
KEY_PATH="$TMPDIR_LOCAL/key.pem"
PUB_PATH="$TMPDIR_LOCAL/key.pub.pem"

cp "$TEST_KEY_FILE" "$KEY_PATH"
python3 <<PY
from pathlib import Path
from cryptography.hazmat.primitives import serialization
key = Path("$KEY_PATH")
priv = serialization.load_pem_private_key(key.read_bytes(), password=None)
pub = priv.public_key()
Path("$PUB_PATH").write_bytes(pub.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
))
PY

export GOV_SIGNING_KEY_PATH="$KEY_PATH"
export GOV_VERIFY_KEY_PATH="$PUB_PATH"

CHAIN="$TMPDIR_LOCAL/decision-chain.jsonl"
TRIAGE="$TMPDIR_LOCAL/triage.record.json"
SUMMARY1="$TMPDIR_LOCAL/summary.pass-triage.json"
SUMMARY2="$TMPDIR_LOCAL/summary.terminal.json"

GOV_DECISION_CHAIN_PATH="$CHAIN" "$PASS_TRIAGE" "$FIXTURES/rdd_category6_authorization_required_input.json" > "$TRIAGE"
python3 "$VERIFY_CHAIN" --summary-json "$SUMMARY1" "$CHAIN" >/dev/null

python3 - <<'PY' "$SUMMARY1"
import json, sys
raw = open(sys.argv[1], encoding="utf-8").read()
assert raw.endswith("\n")
obj = json.loads(raw)
assert obj["report_version"] == "chain_verification_summary_v1"
assert obj["result"] == "PASS"
assert obj["counts"]["records_total"] == 2
assert obj["counts"]["pass_decision"] == 1
assert obj["counts"]["triage_decision"] == 1
assert obj["counts"]["terminal_judgment"] == 0
assert obj["rdd_terminal_process_summary"]["completed_rdd_process_count"] == 0
print("PASS: verify-chain summary json captures pass+triage chain without terminal completion")
PY

GOV_DECISION_CHAIN_PATH="$CHAIN" python3 "$TERMINAL" "$TRIAGE" \
  --method human_authority \
  --outcome ALLOW \
  --decider-identity "product_owner:test" \
  --decider-authority "authorization_grant" \
  --rationale "Summary-json bounded verification path." \
  > /dev/null

python3 "$VERIFY_CHAIN" --summary-json "$SUMMARY2" "$CHAIN" >/dev/null
python3 - <<'PY' "$SUMMARY2"
import json, sys
raw = open(sys.argv[1], encoding="utf-8").read()
assert raw.endswith("\n")
obj = json.loads(raw)
assert obj["report_version"] == "chain_verification_summary_v1"
assert obj["counts"]["records_total"] == 3
assert obj["counts"]["terminal_judgment"] == 1
assert obj["rdd_terminal_process_summary"]["completed_rdd_process_count"] == 1
assert obj["rdd_terminal_process_summary"]["allow_terminal_process_count"] == 1
row = obj["rdd_terminal_process_summary"]["completed_rdd_processes"][0]
assert row["terminal_outcome"] == "ALLOW"
assert row["triage_disposition_type"] == "ESCALATION_JUSTIFIED"
print("PASS: verify-chain summary json captures completed RDD terminal chain")
PY
