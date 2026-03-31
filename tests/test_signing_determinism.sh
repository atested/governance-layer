#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
VERIFY="$ROOT/scripts/verify-record.py"
FIXTURE="$ROOT/tests/fixtures/canon_001a.json"
LOG_DIR="$ROOT/LOGS"

pass=0
fail=0

check_exit () {
  local name="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS: $name (exit=$got)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (exit got=$got, want=$want)"
    fail=$((fail+1))
  fi
}

assert_eq () {
  local name="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS: $name"
    pass=$((pass+1))
  else
    echo "FAIL: $name"
    echo "  got : $got"
    echo "  want: $want"
    fail=$((fail+1))
  fi
}

verify_hash () {
  local name="$1" json_file="$2"
  if "$VERIFY" "$json_file" >/dev/null 2>&1; then
    echo "PASS: $name (record_hash verified)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (record_hash verify failed)"
    "$VERIFY" "$json_file" || true
    fail=$((fail+1))
  fi
}

read_hash () {
  python3 - <<'PY' "$1"
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    print(json.load(f)["record_hash"])
PY
}

mkdir -p "$LOG_DIR"

echo "--- T-SIGNDET-001: record_hash stable across repeated runs ---"
python3 "$EVAL" "$FIXTURE" > "$LOG_DIR/t-signdet-001-a.record.json"
python3 "$EVAL" "$FIXTURE" > "$LOG_DIR/t-signdet-001-b.record.json"

verify_hash "T-SIGNDET-001A verify-record" "$LOG_DIR/t-signdet-001-a.record.json"
verify_hash "T-SIGNDET-001B verify-record" "$LOG_DIR/t-signdet-001-b.record.json"

hash_a="$(read_hash "$LOG_DIR/t-signdet-001-a.record.json")"
hash_b="$(read_hash "$LOG_DIR/t-signdet-001-b.record.json")"
assert_eq "T-SIGNDET-001 same record_hash across runs" "$hash_a" "$hash_b"

echo
echo "--- T-SIGNDET-002: timestamp/UUID/path metadata not in signed payload ---"
python3 - <<'PY' "$LOG_DIR/t-signdet-001-a.record.json" "$LOG_DIR/t-signdet-002-mutated.record.json"
import json, sys

src, dst = sys.argv[1], sys.argv[2]
with open(src, "r", encoding="utf-8") as f:
    rec = json.load(f)

rec["timestamp_utc"] = "2099-12-31T23:59:59Z"
rec["session_id"] = "sess-mutated"
rec["request_id"] = "00000000-0000-0000-0000-000000000000"
rec["prev_record_hash"] = "sha256:" + ("0" * 64)

if isinstance(rec.get("tool_args_redacted"), dict):
    rec["tool_args_redacted"]["path"] = "/tmp/machine-a/secret.txt"
    rec["tool_args_redacted"]["canonical_path"] = "/private/tmp/machine-a/secret.txt"

if isinstance(rec.get("policy_inputs"), dict):
    rec["policy_inputs"]["canonical_path"] = "/private/tmp/machine-b/secret.txt"
    rec["policy_inputs"]["allow_base_dirs"] = ["/opt/hostA/root", "/srv/hostB/root"]

if isinstance(rec.get("normalized_args"), dict):
    if "canonical_path" in rec["normalized_args"]:
        rec["normalized_args"]["canonical_path"] = "/Users/example/other-machine/path.txt"
    if "canonical_src_path" in rec["normalized_args"]:
        rec["normalized_args"]["canonical_src_path"] = "/hostA/src"
    if "canonical_dst_path" in rec["normalized_args"]:
        rec["normalized_args"]["canonical_dst_path"] = "/hostB/dst"

intent = rec.get("intent")
if isinstance(intent, dict) and isinstance(intent.get("expected_outputs"), list):
    for item in intent["expected_outputs"]:
        if isinstance(item, dict) and item.get("ref", "").endswith(":path"):
            item["value"] = "/very/different/machine/dependent/path"

with open(dst, "w", encoding="utf-8") as f:
    json.dump(rec, f, indent=2)
PY

rc_002=0
"$VERIFY" "$LOG_DIR/t-signdet-002-mutated.record.json" >/tmp/t-signdet-verify.out 2>&1 || rc_002=$?
check_exit "T-SIGNDET-002 verify mutated metadata still passes" "$rc_002" "0"
mut_hash="$(read_hash "$LOG_DIR/t-signdet-002-mutated.record.json")"
assert_eq "T-SIGNDET-002 record_hash unchanged after metadata/path mutations" "$mut_hash" "$hash_a"

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
