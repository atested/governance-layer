#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/phase2-machine-report.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

CATALOG="$TMPDIR_LOCAL/catalog.json"
REPORT1="$TMPDIR_LOCAL/report1.json"
REPORT2="$TMPDIR_LOCAL/report2.json"

cat > "$CATALOG" <<'JSON'
{"catalog_version":"verification_catalog_v1","entry_count":4,"entries":[
{"id":"VCAT_OBJ2_AAAA0001","verification_cmd":"bash system/tests/test_phase2_obj2_registry_source_parity.sh"},
{"id":"VCAT_OBJ3_BBBB0002","verification_cmd":"bash system/tests/test_phase2_obj3_reason_precedence_dedup.sh"},
{"id":"VCAT_REGR_CCCC0003","verification_cmd":"bash system/tests/test_phase2_one_command_regression.sh"},
{"id":"VCAT_MERGE_DDDD0004","verification_cmd":"bash system/tests/test_phase2_merge_prep_queue_helper.sh"}
]}
JSON

bash "$ROOT/scripts/dev_phase2_regression.sh" --catalog "$CATALOG" --report "$REPORT1" >/dev/null
bash "$ROOT/scripts/dev_phase2_regression.sh" --catalog "$CATALOG" --report "$REPORT2" >/dev/null

S1="$(shasum -a 256 "$REPORT1" | awk '{print $1}')"
S2="$(shasum -a 256 "$REPORT2" | awk '{print $1}')"
[[ "$S1" == "$S2" ]] || { echo "FAIL: report nondeterministic"; exit 1; }

python3 - "$REPORT1" <<'PY'
import json
import sys
j=json.load(open(sys.argv[1], encoding='utf-8'))
assert j['report_version']=='phase2_report_v1'
ids={r['id'] for r in j['results']}
for expected in ['VCAT_OBJ2_AAAA0001','VCAT_OBJ3_BBBB0002','VCAT_REGR_CCCC0003','VCAT_MERGE_DDDD0004']:
    assert expected in ids
print('CASE=PHASE2_MACHINE_REPORT PASS')
PY

echo "RUN1_SHA256=$S1"
echo "RUN2_SHA256=$S2"
