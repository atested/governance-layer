#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP="out/test_dependency_edges_generation"
rm -rf "$TMP"
mkdir -p "$TMP"

DEPS="$TMP/DEPENDENCY_QUEUE.md"
CAT="$TMP/verification_catalog.v1.json"
REPORT="$TMP/report.v1.json"
OUT1="$TMP/dependency_edges_run1.json"
OUT2="$TMP/dependency_edges_run2.json"

cat > "$DEPS" <<'MD'
# Dependency Queue Proposal (draft)
4) Obj2: unify registry loading path
5) Obj3: precedence/dedup regression tests
6) Roadmap Phase 2 deliverable: one-command regression report artifact
MD

cat > "$CAT" <<'JSON'
{
  "version": "verification_catalog_v1",
  "entries": []
}
JSON

cat > "$REPORT" <<'JSON'
{
  "report_version": "phase2_report_v1",
  "results": [
    {"id":"VCAT_bash_system_tests_test_phase2_obj2_registry_source_parity_sh_b7b6a085","status":"PASS"},
    {"id":"VCAT_bash_system_tests_test_phase2_obj3_reason_precedence_dedup_sh_fe6ff4a9","status":"PASS"},
    {"id":"VCAT_bash_system_tests_test_phase2_one_command_regression_sh_594df2bb","status":"PASS"}
  ]
}
JSON

python3 scripts/dev_generate_dependency_edges.py --deps "$DEPS" --catalog "$CAT" --report "$REPORT" --output "$OUT1" >/dev/null
python3 scripts/dev_generate_dependency_edges.py --deps "$DEPS" --catalog "$CAT" --report "$REPORT" --output "$OUT2" >/dev/null

H1="$(shasum -a 256 "$OUT1" | awk '{print $1}')"
H2="$(shasum -a 256 "$OUT2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

python3 - "$OUT1" <<'PY'
import json, sys
p=sys.argv[1]
d=json.load(open(p))
assert d['version']=='dependency_edges_v1'
assert isinstance(d['edges'], list)
ids={e['id']:e for e in d['edges']}
obj2='VCAT_bash_system_tests_test_phase2_obj2_registry_source_parity_sh_b7b6a085'
obj3='VCAT_bash_system_tests_test_phase2_obj3_reason_precedence_dedup_sh_fe6ff4a9'
reg='VCAT_bash_system_tests_test_phase2_one_command_regression_sh_594df2bb'
assert obj2 in ids and obj3 in ids and reg in ids
assert ids[obj2]['depends_on']==[]
assert ids[obj3]['depends_on']==[obj2]
assert ids[reg]['depends_on']==[obj3]
print('CASE=DEPENDENCY_EDGES_GENERATION PASS')
PY
