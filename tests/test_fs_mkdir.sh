#!/usr/bin/env bash
# test_fs_mkdir.sh — Policy + integrity tests for FS_MKDIR governed tool.
#
# T-MKDIR-001 (ALLOW)
#   Path in allowed root → ALLOW, normalized_args correct, verify-record + replay pass.
#
# T-MKDIR-002 (DENY path)
#   Path outside allowed roots → DENY RC-FS-PATH-DISALLOWED, verify-record + replay pass.
#
# T-POISON-MKDIR-001 (cap_cfg inject)
#   cap_cfg widens allowlist to "/"; evaluator uses internal registry only → DENY.
#   untrusted_inputs contains "cap_cfg".
#
# T-POISON-MKDIR-002 (argv[1] steering)
#   permissive_registry.json as argv[1]; evaluator ignores it → DENY.
#   untrusted_inputs contains cap_registry_path_arg.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
VERIFY="$ROOT/scripts/verify-record.py"
REPLAY="$ROOT/scripts/replay-record.py"
FIXTURES="$ROOT/tests/fixtures"

pass=0
fail=0

assert_contains () {
  local name="$1" json="$2" expect="$3"
  if echo "$json" | grep -q "$expect"; then
    echo "PASS: $name (contains $expect)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (missing $expect)"
    echo "$json"
    fail=$((fail+1))
  fi
}

assert_not_contains () {
  local name="$1" json="$2" absent="$3"
  if echo "$json" | grep -q "$absent"; then
    echo "FAIL: $name (should not contain $absent)"
    fail=$((fail+1))
  else
    echo "PASS: $name (correctly absent: $absent)"
    pass=$((pass+1))
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

replay_check () {
  local name="$1" json_file="$2"
  local rc=0
  local out
  out="$(python3 "$REPLAY" "$json_file" 2>&1)" || rc=$?
  if [[ $rc -eq 0 ]]; then
    echo "PASS: $name (replay exit 0)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (replay exit $rc)"
    echo "$out"
    fail=$((fail+1))
  fi
}

mkdir -p "$ROOT/LOGS"
# Ensure runtime/tmp exists for ALLOW test path
RUNTIME_TMP="${GOV_RUNTIME_PATH:-$ROOT/gov_runtime}/tmp"
mkdir -p "$RUNTIME_TMP"

# ---------------------------------------------------------------------------
# T-MKDIR-001: ALLOW within allowed root
# ---------------------------------------------------------------------------
echo "--- T-MKDIR-001: ALLOW within allowed root ---"

j1="$(python3 "$EVAL" "$FIXTURES/mkdir_allow.json")"
echo "$j1" > "$ROOT/LOGS/t-mkdir-001.record.json"

assert_contains     "T-MKDIR-001 decision ALLOW"       "$j1" '"policy_decision": "ALLOW"'
assert_contains     "T-MKDIR-001 tool FS_MKDIR"         "$j1" '"tool": "FS_MKDIR"'
assert_contains     "T-MKDIR-001 canonical_path"       "$j1" '"canonical_path"'
assert_contains     "T-MKDIR-001 normalized parents"   "$j1" '"parents": false'
assert_contains     "T-MKDIR-001 normalized exist_ok"  "$j1" '"exist_ok": false'
assert_contains     "T-MKDIR-001 cap_registry_hash"    "$j1" '"cap_registry_hash": "sha256:'
assert_contains     "T-MKDIR-001 request_hash"         "$j1" '"request_hash": "sha256:'
verify_hash         "T-MKDIR-001 verify-record"        "$ROOT/LOGS/t-mkdir-001.record.json"
replay_check        "T-MKDIR-001 replay"               "$ROOT/LOGS/t-mkdir-001.record.json"

echo
# ---------------------------------------------------------------------------
# T-MKDIR-002: DENY path outside allowed roots
# ---------------------------------------------------------------------------
echo "--- T-MKDIR-002: DENY outside allowed roots ---"

j2="$(python3 "$EVAL" "$FIXTURES/mkdir_deny_path.json")"
echo "$j2" > "$ROOT/LOGS/t-mkdir-002.record.json"

assert_contains     "T-MKDIR-002 decision DENY"           "$j2" '"policy_decision": "DENY"'
assert_contains     "T-MKDIR-002 reason PATH-DISALLOWED"  "$j2" 'RC-FS-PATH-DISALLOWED'
assert_not_contains "T-MKDIR-002 no ALLOW"                "$j2" '"policy_decision": "ALLOW"'
verify_hash         "T-MKDIR-002 verify-record"           "$ROOT/LOGS/t-mkdir-002.record.json"
replay_check        "T-MKDIR-002 replay"                  "$ROOT/LOGS/t-mkdir-002.record.json"

echo
# ---------------------------------------------------------------------------
# T-POISON-MKDIR-001: cap_cfg inject (widen allowlist to "/")
# ---------------------------------------------------------------------------
echo "--- T-POISON-MKDIR-001: cap_cfg inject ---"

j3="$(python3 "$EVAL" "$FIXTURES/poison_mkdir_capcfg.json")"
echo "$j3" > "$ROOT/LOGS/t-poison-mkdir-001.record.json"

assert_contains     "T-POISON-MKDIR-001 decision DENY"         "$j3" '"policy_decision": "DENY"'
assert_contains     "T-POISON-MKDIR-001 reason PATH-DISALLOWED" "$j3" 'RC-FS-PATH-DISALLOWED'
assert_contains     "T-POISON-MKDIR-001 untrusted cap_cfg"      "$j3" '"cap_cfg"'
assert_not_contains "T-POISON-MKDIR-001 no ALLOW"               "$j3" '"policy_decision": "ALLOW"'
verify_hash         "T-POISON-MKDIR-001 verify-record"          "$ROOT/LOGS/t-poison-mkdir-001.record.json"
replay_check        "T-POISON-MKDIR-001 replay"                 "$ROOT/LOGS/t-poison-mkdir-001.record.json"

echo
# ---------------------------------------------------------------------------
# T-POISON-MKDIR-002: argv[1] permissive registry steering
# Legacy argv[1] = permissive_registry.json; enforcer must ignore it.
# ---------------------------------------------------------------------------
echo "--- T-POISON-MKDIR-002: argv[1] permissive registry steering ---"

j4="$(python3 "$EVAL" "$FIXTURES/permissive_registry.json" "$FIXTURES/mkdir_deny_path.json")"
echo "$j4" > "$ROOT/LOGS/t-poison-mkdir-002.record.json"

assert_contains     "T-POISON-MKDIR-002 decision DENY"              "$j4" '"policy_decision": "DENY"'
assert_contains     "T-POISON-MKDIR-002 reason PATH-DISALLOWED"     "$j4" 'RC-FS-PATH-DISALLOWED'
assert_contains     "T-POISON-MKDIR-002 untrusted registry arg"     "$j4" 'cap_registry_path_arg'
verify_hash         "T-POISON-MKDIR-002 verify-record"              "$ROOT/LOGS/t-poison-mkdir-002.record.json"
replay_check        "T-POISON-MKDIR-002 replay"                     "$ROOT/LOGS/t-poison-mkdir-002.record.json"

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
