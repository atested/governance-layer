#!/usr/bin/env bash
# test_fs_move.sh — Policy + integrity tests for FS_MOVE governed tool.
#
# T-MOVE-001 (ALLOW)
#   Both paths in same allowed root → ALLOW, normalized_args correct,
#   verify-record + replay pass.
#
# T-MOVE-002 (DENY dst outside roots)
#   dst_path outside allowed roots → DENY RC-FS-PATH-DISALLOWED,
#   verify-record + replay pass.
#
# T-MOVE-003 (DENY cross-root)
#   src in runtime root, dst in governance-layer root →
#   DENY RC-FS-CROSS-ROOT-DISALLOWED, verify-record + replay pass.
#
# T-MOVE-004 (DENY overwrite)
#   overwrite=true with caps.overwrite_allowed=false →
#   DENY RC-FS-OVERWRITE-DISALLOWED, verify-record + replay pass.
#
# T-POISON-MOVE-001 (cap_cfg inject)
#   cap_cfg widens allowlist to "/"; evaluator uses internal registry only → DENY.
#   untrusted_inputs contains "cap_cfg".
#
# T-POISON-MOVE-002 (argv[1] steering)
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
# T-MOVE-001: ALLOW within same allowed root
# ---------------------------------------------------------------------------
echo "--- T-MOVE-001: ALLOW within same allowed root ---"

j1="$(python3 "$EVAL" "$FIXTURES/move_allow.json")"
echo "$j1" > "$ROOT/LOGS/t-move-001.record.json"

assert_contains     "T-MOVE-001 decision ALLOW"           "$j1" '"policy_decision": "ALLOW"'
assert_contains     "T-MOVE-001 tool FS_MOVE"             "$j1" '"tool": "FS_MOVE"'
assert_contains     "T-MOVE-001 canonical_src_path"       "$j1" '"canonical_src_path"'
assert_contains     "T-MOVE-001 canonical_dst_path"       "$j1" '"canonical_dst_path"'
assert_contains     "T-MOVE-001 overwrite_requested"      "$j1" '"overwrite_requested": false'
assert_contains     "T-MOVE-001 cap_registry_hash"        "$j1" '"cap_registry_hash": "sha256:'
assert_contains     "T-MOVE-001 request_hash"             "$j1" '"request_hash": "sha256:'
verify_hash         "T-MOVE-001 verify-record"            "$ROOT/LOGS/t-move-001.record.json"
replay_check        "T-MOVE-001 replay"                   "$ROOT/LOGS/t-move-001.record.json"

echo
# ---------------------------------------------------------------------------
# T-MOVE-002: DENY dst path outside allowed roots
# ---------------------------------------------------------------------------
echo "--- T-MOVE-002: DENY dst outside allowed roots ---"

j2="$(python3 "$EVAL" "$FIXTURES/move_deny_dst_path.json")"
echo "$j2" > "$ROOT/LOGS/t-move-002.record.json"

assert_contains     "T-MOVE-002 decision DENY"            "$j2" '"policy_decision": "DENY"'
assert_contains     "T-MOVE-002 reason PATH-DISALLOWED"   "$j2" 'RC-FS-PATH-DISALLOWED'
assert_not_contains "T-MOVE-002 no ALLOW"                 "$j2" '"policy_decision": "ALLOW"'
verify_hash         "T-MOVE-002 verify-record"            "$ROOT/LOGS/t-move-002.record.json"
replay_check        "T-MOVE-002 replay"                   "$ROOT/LOGS/t-move-002.record.json"

echo
# ---------------------------------------------------------------------------
# T-MOVE-003: DENY cross-root move
# ---------------------------------------------------------------------------
echo "--- T-MOVE-003: DENY cross-root move ---"

j3="$(python3 "$EVAL" "$FIXTURES/move_deny_cross_root.json")"
echo "$j3" > "$ROOT/LOGS/t-move-003.record.json"

assert_contains     "T-MOVE-003 decision DENY"               "$j3" '"policy_decision": "DENY"'
assert_contains     "T-MOVE-003 reason CROSS-ROOT"           "$j3" 'RC-FS-CROSS-ROOT-DISALLOWED'
assert_not_contains "T-MOVE-003 no ALLOW"                    "$j3" '"policy_decision": "ALLOW"'
verify_hash         "T-MOVE-003 verify-record"               "$ROOT/LOGS/t-move-003.record.json"
replay_check        "T-MOVE-003 replay"                      "$ROOT/LOGS/t-move-003.record.json"

echo
# ---------------------------------------------------------------------------
# T-MOVE-004: DENY overwrite=true (overwrite_allowed=false)
# ---------------------------------------------------------------------------
echo "--- T-MOVE-004: DENY overwrite disallowed ---"

j4="$(python3 "$EVAL" "$FIXTURES/move_deny_overwrite.json")"
echo "$j4" > "$ROOT/LOGS/t-move-004.record.json"

assert_contains     "T-MOVE-004 decision DENY"               "$j4" '"policy_decision": "DENY"'
assert_contains     "T-MOVE-004 reason OVERWRITE-DISALLOWED" "$j4" 'RC-FS-OVERWRITE-DISALLOWED'
assert_not_contains "T-MOVE-004 no ALLOW"                    "$j4" '"policy_decision": "ALLOW"'
verify_hash         "T-MOVE-004 verify-record"               "$ROOT/LOGS/t-move-004.record.json"
replay_check        "T-MOVE-004 replay"                      "$ROOT/LOGS/t-move-004.record.json"

echo
# ---------------------------------------------------------------------------
# T-POISON-MOVE-001: cap_cfg inject (widen allowlist to "/")
# ---------------------------------------------------------------------------
echo "--- T-POISON-MOVE-001: cap_cfg inject ---"

j5="$(python3 "$EVAL" "$FIXTURES/poison_move_capcfg.json")"
echo "$j5" > "$ROOT/LOGS/t-poison-move-001.record.json"

assert_contains     "T-POISON-MOVE-001 decision DENY"         "$j5" '"policy_decision": "DENY"'
assert_contains     "T-POISON-MOVE-001 reason PATH-DISALLOWED" "$j5" 'RC-FS-PATH-DISALLOWED'
assert_contains     "T-POISON-MOVE-001 untrusted cap_cfg"      "$j5" '"cap_cfg"'
assert_not_contains "T-POISON-MOVE-001 no ALLOW"               "$j5" '"policy_decision": "ALLOW"'
verify_hash         "T-POISON-MOVE-001 verify-record"          "$ROOT/LOGS/t-poison-move-001.record.json"
replay_check        "T-POISON-MOVE-001 replay"                 "$ROOT/LOGS/t-poison-move-001.record.json"

echo
# ---------------------------------------------------------------------------
# T-POISON-MOVE-002: argv[1] permissive registry steering
# Legacy argv[1] = permissive_registry.json; enforcer must ignore it.
# ---------------------------------------------------------------------------
echo "--- T-POISON-MOVE-002: argv[1] permissive registry steering ---"

j6="$(python3 "$EVAL" "$FIXTURES/permissive_registry.json" "$FIXTURES/move_deny_dst_path.json")"
echo "$j6" > "$ROOT/LOGS/t-poison-move-002.record.json"

assert_contains     "T-POISON-MOVE-002 decision DENY"              "$j6" '"policy_decision": "DENY"'
assert_contains     "T-POISON-MOVE-002 reason PATH-DISALLOWED"     "$j6" 'RC-FS-PATH-DISALLOWED'
assert_contains     "T-POISON-MOVE-002 untrusted registry arg"     "$j6" 'cap_registry_path_arg'
verify_hash         "T-POISON-MOVE-002 verify-record"              "$ROOT/LOGS/t-poison-move-002.record.json"
replay_check        "T-POISON-MOVE-002 replay"                     "$ROOT/LOGS/t-poison-move-002.record.json"

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
