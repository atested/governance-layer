#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
REPLAY="$ROOT/scripts/replay-record.py"
FIX="$ROOT/tests/fixtures/coverage_stamp"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/coverage-stamp-replay.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

sha256_audit_normalized() {
  python3 - <<'PY' "$1"
import hashlib, json, sys
doc = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
for rec in doc.get('records', []):
    if isinstance(rec, dict) and 'record_path' in rec:
        rec['record_path'] = '<record>'
payload = json.dumps(doc, sort_keys=True, separators=(',', ':')).encode('utf-8')
print(hashlib.sha256(payload).hexdigest())
PY
}

build_intent() {
  local fixture_name="$1"
  local include_stamp="$2"
  local out="$3"
  python3 - <<'PY' "$ROOT" "$FIX" "$fixture_name" "$include_stamp" "$out"
import json,sys,pathlib
root=pathlib.Path(sys.argv[1])
fix=pathlib.Path(sys.argv[2])
fixture_name=sys.argv[3]
include_stamp=(sys.argv[4] == '1')
out=pathlib.Path(sys.argv[5])
intent={
  'tool':'FS_READ',
  'args':{'path':str(root/'capabilities'/'capability-registry.json'),'max_bytes':4096,'offset':0,'as_text':True},
  'intent':{'goal':'Coverage stamp replay regression','constraints':{},'requested_action':'FS_READ','inputs':[],'expected_outputs':[{'ref':'file:path','value':str(root/'capabilities'/'capability-registry.json')}]},
}
if include_stamp:
    intent['coverage_stamp']=json.loads((fix/fixture_name).read_text(encoding='utf-8'))
out.write_text(json.dumps(intent, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
PY
}

normalize_out() {
  local infile="$1"
  local outfile="$2"
  sed -E 's#record=[^,)]*#record=<record>#g' "$infile" > "$outfile"
}

assert_contains() {
  local label="$1" hay="$2" needle="$3"
  if [[ "$hay" != *"$needle"* ]]; then
    echo "FAIL: $label (missing '$needle')"
    exit 1
  fi
}

echo "--- T-COVERAGE-REPLAY-001: required complete coverage replay pass deterministic ---"
build_intent complete_v1.json 1 "$TMPDIR_LOCAL/intent_complete.json"
GOV_COVERAGE_STAMP_REQUIRED=1 python3 "$EVAL" "$TMPDIR_LOCAL/intent_complete.json" > "$TMPDIR_LOCAL/record_complete.json"
python3 "$REPLAY" --require-coverage-stamp --audit-report-json "$TMPDIR_LOCAL/audit_pass1.json" "$TMPDIR_LOCAL/record_complete.json" > "$TMPDIR_LOCAL/pass1.raw"
python3 "$REPLAY" --require-coverage-stamp --audit-report-json "$TMPDIR_LOCAL/audit_pass2.json" "$TMPDIR_LOCAL/record_complete.json" > "$TMPDIR_LOCAL/pass2.raw"
normalize_out "$TMPDIR_LOCAL/pass1.raw" "$TMPDIR_LOCAL/pass1.out"
normalize_out "$TMPDIR_LOCAL/pass2.raw" "$TMPDIR_LOCAL/pass2.out"
P1="$(sha256_file "$TMPDIR_LOCAL/pass1.out")"
P2="$(sha256_file "$TMPDIR_LOCAL/pass2.out")"
A1="$(sha256_audit_normalized "$TMPDIR_LOCAL/audit_pass1.json")"
A2="$(sha256_audit_normalized "$TMPDIR_LOCAL/audit_pass2.json")"
[[ "$P1" == "$P2" ]] || { echo "FAIL: replay pass stdout nondeterministic"; exit 1; }
[[ "$A1" == "$A2" ]] || { echo "FAIL: replay pass audit report nondeterministic"; exit 1; }
PASS_OUT="$(cat "$TMPDIR_LOCAL/pass1.out")"
assert_contains "replay pass marker" "$PASS_OUT" "PASS: replay matches original"
assert_contains "replay coverage summary" "$PASS_OUT" "Coverage Summary: overall_status=complete reason_code=COVERAGE_STAMP_OK"
python3 - <<'PY' "$TMPDIR_LOCAL/audit_pass1.json"
import json,sys
report=json.load(open(sys.argv[1], 'r', encoding='utf-8'))
assert report['record_counts']['matched'] == 1
print('PASS: replay audit report deterministic and matched=1')
PY

echo "--- T-COVERAGE-REPLAY-002: required missing stamp fail-closed deterministic ---"
build_intent missing_required.json 0 "$TMPDIR_LOCAL/intent_missing.json"
GOV_COVERAGE_STAMP_REQUIRED=0 python3 "$EVAL" "$TMPDIR_LOCAL/intent_missing.json" > "$TMPDIR_LOCAL/record_missing.json"
set +e
python3 "$REPLAY" --require-coverage-stamp "$TMPDIR_LOCAL/record_missing.json" > "$TMPDIR_LOCAL/miss1.raw" 2>&1
MRC1=$?
python3 "$REPLAY" --require-coverage-stamp "$TMPDIR_LOCAL/record_missing.json" > "$TMPDIR_LOCAL/miss2.raw" 2>&1
MRC2=$?
set -e
[[ "$MRC1" == "1" && "$MRC2" == "1" ]] || { echo "FAIL: expected rc=1 for missing stamp got rc1=$MRC1 rc2=$MRC2"; exit 1; }
normalize_out "$TMPDIR_LOCAL/miss1.raw" "$TMPDIR_LOCAL/miss1.out"
normalize_out "$TMPDIR_LOCAL/miss2.raw" "$TMPDIR_LOCAL/miss2.out"
M1="$(sha256_file "$TMPDIR_LOCAL/miss1.out")"
M2="$(sha256_file "$TMPDIR_LOCAL/miss2.out")"
[[ "$M1" == "$M2" ]] || { echo "FAIL: replay missing stdout nondeterministic"; exit 1; }
MISS_OUT="$(cat "$TMPDIR_LOCAL/miss1.out")"
assert_contains "replay missing reason" "$MISS_OUT" "COVERAGE_STAMP_MISSING"

echo "--- T-COVERAGE-REPLAY-003: optional absent stamp deterministic behavior ---"
python3 "$REPLAY" "$TMPDIR_LOCAL/record_missing.json" > "$TMPDIR_LOCAL/opt1.raw"
python3 "$REPLAY" "$TMPDIR_LOCAL/record_missing.json" > "$TMPDIR_LOCAL/opt2.raw"
normalize_out "$TMPDIR_LOCAL/opt1.raw" "$TMPDIR_LOCAL/opt1.out"
normalize_out "$TMPDIR_LOCAL/opt2.raw" "$TMPDIR_LOCAL/opt2.out"
O1="$(sha256_file "$TMPDIR_LOCAL/opt1.out")"
O2="$(sha256_file "$TMPDIR_LOCAL/opt2.out")"
[[ "$O1" == "$O2" ]] || { echo "FAIL: replay optional-absent stdout nondeterministic"; exit 1; }
OPT_OUT="$(cat "$TMPDIR_LOCAL/opt1.out")"
assert_contains "replay optional summary" "$OPT_OUT" "Coverage Summary: overall_status=missing reason_code=COVERAGE_STAMP_MISSING"
assert_contains "replay optional pass" "$OPT_OUT" "PASS: replay matches original"

echo "COVERAGE_REPLAY_PASS_SHA256_RUN1=$P1"
echo "COVERAGE_REPLAY_PASS_SHA256_RUN2=$P2"
echo "COVERAGE_REPLAY_PASS_AUDIT_SHA256_RUN1=$A1"
echo "COVERAGE_REPLAY_PASS_AUDIT_SHA256_RUN2=$A2"
echo "COVERAGE_REPLAY_MISSING_SHA256_RUN1=$M1"
echo "COVERAGE_REPLAY_MISSING_SHA256_RUN2=$M2"
echo "COVERAGE_REPLAY_OPTIONAL_SHA256_RUN1=$O1"
echo "COVERAGE_REPLAY_OPTIONAL_SHA256_RUN2=$O2"
echo "Summary: coverage stamp replay contract checks complete"
