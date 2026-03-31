#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REG="$ROOT/capabilities/capability-registry.json"
EVAL="$ROOT/scripts/policy-eval.py"
FIX1="$ROOT/tests/fixtures/fs_missing_intent_goal.json"
FIX2="$ROOT/tests/fixtures/fs_missing_intent_expected_outputs.json"

run_case() {
  local name="$1"
  local fixture="$2"

  echo "--- $name ---"
  echo "$ python3 $EVAL $REG $fixture"
  local out
  out="$(python3 "$EVAL" "$REG" "$fixture")"
  python3 - <<'PY' "$out"
import json, sys
obj = json.loads(sys.argv[1])
print(f"policy_decision={obj.get('policy_decision')}")
import json
print("policy_reasons_json=" + json.dumps(obj.get("policy_reasons", []), sort_keys=True, separators=(",", ":")))
PY

  echo "$out" | grep -q '"policy_decision": "DENY"'
  echo "$out" | grep -q 'RC-FS-MISSING-INTENT-FIELDS'
}

run_case "TASK_066 missing intent.goal" "$FIX1"
run_case "TASK_066 missing intent.expected_outputs" "$FIX2"

echo "PASS: both fixtures DENY with RC-FS-MISSING-INTENT-FIELDS"
