#!/usr/bin/env bash
# test_poisoned_intent.sh — Verify policy-eval ignores caller-supplied cap_cfg.
#
# Test 1 (T-POISON-001): Unknown tool injection
#   cap_cfg claims FS_DELETE is allowed; evaluator must deny with RC-UNKNOWN-TOOL.
#
# Test 2 (T-POISON-002): Weaken caps for FS_WRITE
#   cap_cfg loosens allowlist to "/"; evaluator must deny with RC-FS-PATH-DISALLOWED.
#
# Both tests additionally verify:
#   - cap_registry_hash is bound to the real on-disk registry
#   - untrusted_inputs includes "cap_cfg"
#   - verify-record.py passes on the produced decision record
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
VERIFY="$ROOT/scripts/verify-record.py"
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
    echo "FAIL: $name (should not contain $absent but does)"
    echo "$json"
    fail=$((fail+1))
  else
    echo "PASS: $name (correctly absent: $absent)"
    pass=$((pass+1))
  fi
}

verify_hash () {
  local name="$1" json_file="$2"
  if ! grep -q '"cap_registry_hash"' "$json_file"; then
    echo "FAIL: $name (missing cap_registry_hash field)"
    fail=$((fail+1))
    return
  fi
  if "$VERIFY" "$json_file" >/dev/null; then
    echo "PASS: $name (record_hash verified)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (record_hash verify failed)"
    cat "$json_file"
    fail=$((fail+1))
  fi
}

mkdir -p "$ROOT/LOGS"

# ---------------------------------------------------------------------------
# T-POISON-001: Unknown tool injection
# cap_cfg claims FS_DELETE is registered; evaluator must use internal registry
# and deny with RC-UNKNOWN-TOOL.
# ---------------------------------------------------------------------------
echo "--- T-POISON-001: unknown tool injection ---"
j1="$("$EVAL" "$FIXTURES/poison_capcfg_unknown_tool.json")"
echo "$j1" > "$ROOT/LOGS/t-poison-001.record.json"

assert_contains  "T-POISON-001 decision DENY"         "$j1" '"policy_decision": "DENY"'
assert_contains  "T-POISON-001 reason unknown tool"   "$j1" 'RC-UNKNOWN-TOOL'
assert_not_contains "T-POISON-001 no RC-FS-PATH-DISALLOWED" "$j1" 'RC-FS-PATH-DISALLOWED'
assert_contains  "T-POISON-001 untrusted_inputs cap_cfg" "$j1" '"cap_cfg"'
verify_hash      "T-POISON-001 hash" "$ROOT/LOGS/t-poison-001.record.json"

echo
# ---------------------------------------------------------------------------
# T-POISON-002: Weaken caps injection
# cap_cfg claims FS_WRITE allows all paths; evaluator must enforce real allowlist
# and deny with RC-FS-PATH-DISALLOWED (path is /tmp which is outside allowlist).
# ---------------------------------------------------------------------------
echo "--- T-POISON-002: weaken caps injection ---"
j2="$("$EVAL" "$FIXTURES/poison_capcfg_weaken_caps.json")"
echo "$j2" > "$ROOT/LOGS/t-poison-002.record.json"

assert_contains  "T-POISON-002 decision DENY"              "$j2" '"policy_decision": "DENY"'
assert_contains  "T-POISON-002 reason path disallowed"     "$j2" 'RC-FS-PATH-DISALLOWED'
assert_contains  "T-POISON-002 untrusted_inputs cap_cfg"   "$j2" '"cap_cfg"'
verify_hash      "T-POISON-002 hash" "$ROOT/LOGS/t-poison-002.record.json"

echo
# ---------------------------------------------------------------------------
# T-POISON-003: Legacy argv[1] steering attempt
# Call policy-eval with a permissive registry as argv[1].
# The intent requests FS_WRITE to /tmp — allowed by permissive_registry.json
# but denied by the real internal registry.
# Expected: DENY RC-FS-PATH-DISALLOWED, untrusted_inputs includes cap_registry_path_arg.
# ---------------------------------------------------------------------------
echo "--- T-POISON-003: argv[1] permissive registry steering ---"
j3="$("$EVAL" "$FIXTURES/permissive_registry.json" "$FIXTURES/poison_capcfg_weaken_caps.json")"
echo "$j3" > "$ROOT/LOGS/t-poison-003.record.json"

assert_contains  "T-POISON-003 decision DENY"                  "$j3" '"policy_decision": "DENY"'
assert_contains  "T-POISON-003 reason path disallowed"         "$j3" 'RC-FS-PATH-DISALLOWED'
assert_contains  "T-POISON-003 untrusted_inputs registry arg"  "$j3" 'cap_registry_path_arg'
assert_contains  "T-POISON-003 path arg logged"                "$j3" 'permissive_registry'
verify_hash      "T-POISON-003 hash" "$ROOT/LOGS/t-poison-003.record.json"

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
