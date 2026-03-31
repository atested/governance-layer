#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REG="$ROOT/capabilities/capability-registry.json"
EVAL="$ROOT/scripts/policy-eval.py"
FIXTURE="$ROOT/tests/fixtures/fs_list_include_hidden_disallowed.json"

echo "--- TASK_094: RC-FS-INCLUDE-HIDDEN-DISALLOWED ---"
echo "$ python3 $EVAL $REG $FIXTURE"
out="$(python3 "$EVAL" "$REG" "$FIXTURE")"
python3 - <<'PY' "$out"
import json, sys
obj = json.loads(sys.argv[1])
print(f"policy_decision={obj.get('policy_decision')}")
import json
print("policy_reasons_json=" + json.dumps(obj.get("policy_reasons", []), sort_keys=True, separators=(",", ":")))
PY

echo "$out" | grep -q '"policy_decision": "DENY"'
echo "$out" | grep -q 'RC-FS-INCLUDE-HIDDEN-DISALLOWED'

echo "PASS: decision DENY with RC-FS-INCLUDE-HIDDEN-DISALLOWED"
