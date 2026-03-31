#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_DIR="out/test_next_actions_compiler"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

STATUS_JSON="$TMP_DIR/status.v1.json"
CATALOG_JSON="$TMP_DIR/verification_catalog.v1.json"
DEPS_MD="$TMP_DIR/DEPENDENCY_QUEUE.md"
EDGES_JSON="$TMP_DIR/dependency_edges.v1.json"
OUT1="$TMP_DIR/next_actions_run1.json"
OUT2="$TMP_DIR/next_actions_run2.json"

cat > "$STATUS_JSON" <<'JSON'
{
  "open_verifications": [
    {"id":"VCAT_bash_system_tests_test_phase2_obj3_reason_precedence_dedup_sh_fe6ff4a9","status":"SKIP"},
    {"id":"VCAT_bash_system_tests_test_phase2_one_command_regression_sh_594df2bb","status":"SKIP"},
    {"id":"VCAT_A","status":"FAIL"}
  ],
  "blocked_by_dependencies": [
    {"id":"VCAT_bash_system_tests_test_phase2_obj3_reason_precedence_dedup_sh_fe6ff4a9","dependency_token":"OBJ3_DEP"},
    {"id":"VCAT_bash_system_tests_test_phase2_one_command_regression_sh_594df2bb","dependency_token":"REGRESSION_DEP"}
  ]
}
JSON

cat > "$CATALOG_JSON" <<'JSON'
{
  "version": "verification_catalog_v1",
  "entries": [
    {"id":"VCAT_A","title":"A","objective":"OBJ1","verification_cmd":"bash system/tests/test_a.sh","description":"A"},
    {"id":"VCAT_bash_system_tests_test_phase2_obj2_registry_source_parity_sh_b7b6a085","title":"Obj2","objective":"OBJ2","verification_cmd":"bash system/tests/test_phase2_obj2_registry_source_parity.sh","description":"Obj2"},
    {"id":"VCAT_bash_system_tests_test_phase2_obj3_reason_precedence_dedup_sh_fe6ff4a9","title":"Obj3","objective":"OBJ3","verification_cmd":"bash system/tests/test_phase2_obj3_reason_precedence_dedup.sh","description":"Obj3"},
    {"id":"VCAT_bash_system_tests_test_phase2_one_command_regression_sh_594df2bb","title":"Regression","objective":"REGRESSION","verification_cmd":"bash system/tests/test_phase2_one_command_regression.sh","description":"Regression"}
  ]
}
JSON

cat > "$DEPS_MD" <<'MD'
# Dependency Queue
4) Obj2
5) Obj3
6) Roadmap Phase 2 deliverable: one-command regression report artifact
MD

cat > "$EDGES_JSON" <<'JSON'
{
  "version": "dependency_edges_v1",
  "edges": [
    {"id":"VCAT_bash_system_tests_test_phase2_obj2_registry_source_parity_sh_b7b6a085","depends_on":[]},
    {"id":"VCAT_bash_system_tests_test_phase2_obj3_reason_precedence_dedup_sh_fe6ff4a9","depends_on":["VCAT_bash_system_tests_test_phase2_obj2_registry_source_parity_sh_b7b6a085"]},
    {"id":"VCAT_bash_system_tests_test_phase2_one_command_regression_sh_594df2bb","depends_on":["VCAT_bash_system_tests_test_phase2_obj3_reason_precedence_dedup_sh_fe6ff4a9"]}
  ]
}
JSON

bash scripts/dev_next_actions_compiler.sh \
  --status-file "$STATUS_JSON" \
  --catalog-file "$CATALOG_JSON" \
  --deps-file "$DEPS_MD" \
  --edges-file "$EDGES_JSON" \
  --out-file "$OUT1" >/dev/null

bash scripts/dev_next_actions_compiler.sh \
  --status-file "$STATUS_JSON" \
  --catalog-file "$CATALOG_JSON" \
  --deps-file "$DEPS_MD" \
  --edges-file "$EDGES_JSON" \
  --out-file "$OUT2" >/dev/null

HASH1="$(python3 - "$OUT1" <<'PY'
import hashlib, json, pathlib, sys
p = pathlib.Path(sys.argv[1])
d = json.loads(p.read_text())
s = json.dumps(d, sort_keys=True, separators=(",",":"))
print(hashlib.sha256(s.encode()).hexdigest())
PY
)"
HASH2="$(python3 - "$OUT2" <<'PY'
import hashlib, json, pathlib, sys
p = pathlib.Path(sys.argv[1])
d = json.loads(p.read_text())
s = json.dumps(d, sort_keys=True, separators=(",",":"))
print(hashlib.sha256(s.encode()).hexdigest())
PY
)"
[[ "$HASH1" == "$HASH2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

python3 - "$OUT1" <<'PY'
import json, sys
rows = json.load(open(sys.argv[1]))['open']
req = ["id","status","action","reason_token","depends_on","cmd"]
for r in rows:
    for k in req:
        assert k in r

obj3 = next(r for r in rows if r['id']=='VCAT_bash_system_tests_test_phase2_obj3_reason_precedence_dedup_sh_fe6ff4a9')
reg = next(r for r in rows if r['id']=='VCAT_bash_system_tests_test_phase2_one_command_regression_sh_594df2bb')
assert obj3['reason_token']=='DEP_BLOCKED'
assert reg['reason_token']=='DEP_BLOCKED'
assert obj3['depends_on']==['VCAT_bash_system_tests_test_phase2_obj2_registry_source_parity_sh_b7b6a085']
assert reg['depends_on']==['VCAT_bash_system_tests_test_phase2_obj3_reason_precedence_dedup_sh_fe6ff4a9']
assert obj3['reason_token']!='MISSING_DEPENDENCY_EDGE'
assert reg['reason_token']!='MISSING_DEPENDENCY_EDGE'
print('CASE=NEXT_ACTIONS_COMPILER PASS')
PY
