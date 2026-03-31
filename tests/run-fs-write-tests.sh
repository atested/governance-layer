#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REG="$ROOT/capabilities/capability-registry.json"
EVAL="$ROOT/scripts/policy-eval.py"
VERIFY="$ROOT/scripts/verify-record.py"

pass=0
fail=0

run_eval () {
  local intent_file="$1"
  "$EVAL" "$REG" "$intent_file"
}

assert_contains () {
  local name="$1"
  local json="$2"
  local expect="$3"
  if echo "$json" | grep -q "$expect"; then
    echo "PASS: $name (contains $expect)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (missing $expect)"
    echo "$json"
    fail=$((fail+1))
  fi
}

assert_order_first_two_codes () {
  local name="$1"
  local json="$2"
  local first="$3"
  local second="$4"

  local codes
  codes="$(echo "$json" | awk '/"policy_reasons"/{flag=1;next} flag && /"code":/{gsub(/.*"code":[[:space:]]*"/,""); gsub(/".*/,""); print} flag && /]/{exit}')"
  local c1 c2
  c1="$(echo "$codes" | sed -n '1p')"
  c2="$(echo "$codes" | sed -n '2p')"

  if [[ "$c1" == "$first" && "$c2" == "$second" ]]; then
    echo "PASS: $name (order $first then $second)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (expected order $first then $second)"
    echo "$json"
    fail=$((fail+1))
  fi
}

verify_hash () {
  local name="$1"
  local json_file="$2"
  # Assert cap_registry_hash field exists
  if ! grep -q '"cap_registry_hash"' "$json_file"; then
    echo "FAIL: $name (missing cap_registry_hash field)"
    cat "$json_file"
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

# T-FS-001 Disallowed base path
cat > "$ROOT/LOGS/t-fs-001.json" <<'JSON'
{
  "intent": {
    "goal": "Attempt write outside allowlist.",
    "constraints": { "overwrite": false },
    "requested_action": "FS_WRITE",
    "inputs": [],
    "expected_outputs": [{"ref":"file:path","value":"/Volumes/SSD/archive/NOT_ALLOWED/out.txt"}]
  },
  "tool": "FS_WRITE",
  "args": { "path": "/Volumes/SSD/archive/NOT_ALLOWED/out.txt", "content": "x", "request_executable": false }
}
JSON

# T-FS-002 Hidden path
cat > "$ROOT/LOGS/t-fs-002.json" <<'JSON'
{
  "intent": {
    "goal": "Attempt write to hidden path inside repo.",
    "constraints": { "overwrite": false },
    "requested_action": "FS_WRITE",
    "inputs": [],
    "expected_outputs": [{"ref":"file:path","value":"/Volumes/SSD/archive/gov/governance-layer/.ssh/config"}]
  },
  "tool": "FS_WRITE",
  "args": { "path": "/Volumes/SSD/archive/gov/governance-layer/.ssh/config", "content": "x", "request_executable": false }
}
JSON

# T-FS-003 Traversal attempt into hidden path
cat > "$ROOT/LOGS/t-fs-003.json" <<'JSON'
{
  "intent": {
    "goal": "Attempt traversal into hidden path.",
    "constraints": { "overwrite": false },
    "requested_action": "FS_WRITE",
    "inputs": [],
    "expected_outputs": [{"ref":"file:path","value":"/Volumes/SSD/archive/gov/governance-layer/docs/../.git/config"}]
  },
  "tool": "FS_WRITE",
  "args": { "path": "/Volumes/SSD/archive/gov/governance-layer/docs/../.git/config", "content": "x", "request_executable": false }
}
JSON

# T-FS-004 Overwrite mismatch (intent says overwrite true but args overwrite false)
cat > "$ROOT/LOGS/t-fs-004.json" <<'JSON'
{
  "intent": {
  "goal": "Attempt overwrite without explicit args overwrite.",
    "constraints": { "overwrite": true },
    "requested_action": "FS_WRITE",
    "inputs": [],
    "expected_outputs": [{"ref":"file:path","value":"/Volumes/SSD/archive/gov/governance-layer/docs/SCOPE.md"}]
  },
  "tool": "FS_WRITE",
  "args": { "path": "/Volumes/SSD/archive/gov/governance-layer/docs/SCOPE.md", "content": "x", "request_executable": false, "overwrite": false }
}
JSON

# Run and persist decision records
run_eval "$ROOT/LOGS/t-fs-001.json" > "$ROOT/LOGS/t-fs-001.record.json"
run_eval "$ROOT/LOGS/t-fs-002.json" > "$ROOT/LOGS/t-fs-002.record.json"
run_eval "$ROOT/LOGS/t-fs-003.json" > "$ROOT/LOGS/t-fs-003.record.json"
run_eval "$ROOT/LOGS/t-fs-004.json" > "$ROOT/LOGS/t-fs-004.record.json"

j1="$(cat "$ROOT/LOGS/t-fs-001.record.json")"
j2="$(cat "$ROOT/LOGS/t-fs-002.record.json")"
j3="$(cat "$ROOT/LOGS/t-fs-003.record.json")"
j4="$(cat "$ROOT/LOGS/t-fs-004.record.json")"

assert_contains "T-FS-001 decision DENY" "$j1" '"policy_decision": "DENY"'
assert_contains "T-FS-001 reason path disallowed" "$j1" 'RC-FS-PATH-DISALLOWED'
verify_hash "T-FS-001 hash" "$ROOT/LOGS/t-fs-001.record.json"

assert_contains "T-FS-002 decision DENY" "$j2" '"policy_decision": "DENY"'
assert_contains "T-FS-002 reason hidden path" "$j2" 'RC-FS-HIDDEN-PATH'
verify_hash "T-FS-002 hash" "$ROOT/LOGS/t-fs-002.record.json"

assert_contains "T-FS-003 decision DENY" "$j3" '"policy_decision": "DENY"'
assert_order_first_two_codes "T-FS-003 precedence traversal then disallowed" "$j3" "RC-FS-PATH-TRAVERSAL" "RC-FS-PATH-DISALLOWED"
assert_contains "T-FS-003 also reports hidden path" "$j3" 'RC-FS-HIDDEN-PATH'
verify_hash "T-FS-003 hash" "$ROOT/LOGS/t-fs-003.record.json"

assert_contains "T-FS-004 decision DENY" "$j4" '"policy_decision": "DENY"'
assert_contains "T-FS-004 reason overwrite disallowed" "$j4" 'RC-FS-OVERWRITE-DISALLOWED'
verify_hash "T-FS-004 hash" "$ROOT/LOGS/t-fs-004.record.json"

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
