#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
FIX="$ROOT/tests/fixtures"
pass=0; fail=0
a(){ if echo "$2" | grep -q "$3"; then echo "PASS: $1"; pass=$((pass+1)); else echo "FAIL: $1"; echo "$2"; fail=$((fail+1)); fi; }
n(){ if echo "$2" | grep -q "$3"; then echo "FAIL: $1"; fail=$((fail+1)); else echo "PASS: $1"; pass=$((pass+1)); fi; }

echo "--- T-DELETE-001: ALLOW file within allowed root ---"
j1="$(python3 "$EVAL" "$FIX/delete_allow.json")"
a "T-DELETE-001 decision ALLOW" "$j1" '"policy_decision": "ALLOW"'
a "T-DELETE-001 tool FS_DELETE" "$j1" '"tool": "FS_DELETE"'
a "T-DELETE-001 normalized path" "$j1" '"canonical_path"'

echo "--- T-DELETE-002: DENY path outside allowed roots ---"
j2="$(python3 "$EVAL" "$FIX/delete_deny_path.json")"
a "T-DELETE-002 decision DENY" "$j2" '"policy_decision": "DENY"'
a "T-DELETE-002 RC PATH-DISALLOWED" "$j2" 'RC-FS-PATH-DISALLOWED'
n "T-DELETE-002 no ALLOW" "$j2" '"policy_decision": "ALLOW"'

echo "--- T-DELETE-003: DENY hidden path segment ---"
j3="$(python3 "$EVAL" "$FIX/delete_deny_hidden.json")"
a "T-DELETE-003 decision DENY" "$j3" '"policy_decision": "DENY"'
a "T-DELETE-003 RC HIDDEN-PATH" "$j3" 'RC-FS-HIDDEN-PATH'

echo "--- T-DELETE-004: DENY recursive disallowed ---"
j4="$(python3 "$EVAL" "$FIX/delete_deny_recursive.json")"
a "T-DELETE-004 decision DENY" "$j4" '"policy_decision": "DENY"'
a "T-DELETE-004 RC RECURSIVE-DISALLOWED" "$j4" 'RC-FS-RECURSIVE-DISALLOWED'
n "T-DELETE-004 no ALLOW" "$j4" '"policy_decision": "ALLOW"'

echo "--- T-POISON-DELETE-001: cap_cfg inject ---"
j5="$(python3 "$EVAL" "$FIX/poison_delete_capcfg.json")"
a "T-POISON-DELETE-001 decision DENY" "$j5" '"policy_decision": "DENY"'
a "T-POISON-DELETE-001 RC PATH-DISALLOWED" "$j5" 'RC-FS-PATH-DISALLOWED'
a "T-POISON-DELETE-001 untrusted cap_cfg" "$j5" '"cap_cfg"'

echo "--- T-POISON-DELETE-002: argv[1] permissive registry steering ---"
j6="$(python3 "$EVAL" "$FIX/permissive_registry.json" "$FIX/delete_deny_path.json")"
a "T-POISON-DELETE-002 decision DENY" "$j6" '"policy_decision": "DENY"'
a "T-POISON-DELETE-002 RC PATH-DISALLOWED" "$j6" 'RC-FS-PATH-DISALLOWED'
a "T-POISON-DELETE-002 untrusted registry arg" "$j6" 'cap_registry_path_arg'

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
