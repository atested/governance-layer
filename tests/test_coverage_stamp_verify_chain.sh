#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
CHAIN="$ROOT/scripts/verify-chain.py"
FIX="$ROOT/tests/fixtures/coverage_stamp"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/coverage-stamp-chain.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

build_intent_complete() {
  python3 - <<'PY' "$ROOT" "$FIX/complete_v1.json" "$1"
import json,sys,pathlib
root=pathlib.Path(sys.argv[1])
stamp=json.loads(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8'))
out=pathlib.Path(sys.argv[3])
intent={
  'tool':'FS_READ',
  'args':{'path':str(root/'capabilities'/'capability-registry.json'),'max_bytes':4096,'offset':0,'as_text':True},
  'intent':{'goal':'Coverage stamp verify-chain regression','constraints':{},'requested_action':'FS_READ','inputs':[],'expected_outputs':[{'ref':'file:path','value':str(root/'capabilities'/'capability-registry.json')}]},
  'coverage_stamp': stamp,
}
out.write_text(json.dumps(intent, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
PY
}

record_hash() {
  python3 - <<'PY' "$1"
import json,sys
print(json.loads(open(sys.argv[1], 'r', encoding='utf-8').read())['record_hash'])
PY
}

mutate_record_fixture() {
  local src="$1"
  local fixture_name="$2"
  local include_stamp="$3"
  local out="$4"
  python3 - <<'PY' "$ROOT" "$src" "$FIX" "$fixture_name" "$include_stamp" "$out"
import importlib.util, json, sys, pathlib
root=pathlib.Path(sys.argv[1])
src=pathlib.Path(sys.argv[2])
fix=pathlib.Path(sys.argv[3])
fixture=sys.argv[4]
include_stamp=sys.argv[5] == '1'
out=pathlib.Path(sys.argv[6])
spec = importlib.util.spec_from_file_location('verify_record_impl', root / 'scripts' / 'verify-record.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
doc=json.loads(src.read_text(encoding='utf-8'))
if include_stamp:
    doc['coverage_stamp']=json.loads((fix/fixture).read_text(encoding='utf-8'))
else:
    doc.pop('coverage_stamp', None)
doc['record_hash'] = 'sha256:' + mod.sha256_hex(mod.signing_preimage_payload(doc))
doc['signature'] = None
doc['signing_key_id'] = None
out.write_text(json.dumps(doc, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
PY
}

make_chain_jsonl() {
  local out="$1"
  shift
  python3 - <<'PY' "$out" "$@"
import json,sys,pathlib
out=pathlib.Path(sys.argv[1])
paths=[pathlib.Path(p) for p in sys.argv[2:]]
with out.open('w', encoding='utf-8') as f:
    for p in paths:
        doc=json.loads(p.read_text(encoding='utf-8'))
        f.write(json.dumps(doc, sort_keys=True, separators=(',', ':')) + '\n')
PY
}

assert_contains() {
  local label="$1" hay="$2" needle="$3"
  if [[ "$hay" != *"$needle"* ]]; then
    echo "FAIL: $label (missing '$needle')"
    exit 1
  fi
}

echo "--- T-COVERAGE-CHAIN-001: complete chain includes canonical per-record coverage status ---"
build_intent_complete "$TMPDIR_LOCAL/intent_complete.json"
GOV_COVERAGE_STAMP_REQUIRED=1 python3 "$EVAL" "$TMPDIR_LOCAL/intent_complete.json" > "$TMPDIR_LOCAL/r1.json"
H1="$(record_hash "$TMPDIR_LOCAL/r1.json")"
GOV_COVERAGE_STAMP_REQUIRED=1 GOV_PREV_RECORD_HASH="$H1" python3 "$EVAL" "$TMPDIR_LOCAL/intent_complete.json" > "$TMPDIR_LOCAL/r2.json"
make_chain_jsonl "$TMPDIR_LOCAL/chain_ok.jsonl" "$TMPDIR_LOCAL/r1.json" "$TMPDIR_LOCAL/r2.json"
python3 "$CHAIN" --require-coverage-stamp "$TMPDIR_LOCAL/chain_ok.jsonl" > "$TMPDIR_LOCAL/ok1.out"
python3 "$CHAIN" --require-coverage-stamp "$TMPDIR_LOCAL/chain_ok.jsonl" > "$TMPDIR_LOCAL/ok2.out"
OK1="$(sha256_file "$TMPDIR_LOCAL/ok1.out")"
OK2="$(sha256_file "$TMPDIR_LOCAL/ok2.out")"
[[ "$OK1" == "$OK2" ]] || { echo "FAIL: verify-chain complete output nondeterministic"; exit 1; }
OUT_OK="$(cat "$TMPDIR_LOCAL/ok1.out")"
assert_contains "chain pass" "$OUT_OK" "PASS: chain verified (2 records)"
assert_contains "chain row1" "$OUT_OK" "coverage_record line=1 overall_status=complete reason_code=COVERAGE_STAMP_OK"
assert_contains "chain row2" "$OUT_OK" "coverage_record line=2 overall_status=complete reason_code=COVERAGE_STAMP_OK"
assert_contains "chain summary" "$OUT_OK" "Coverage Summary: ok=2 partial=0 missing_or_absent=0"
echo "PASS: complete chain deterministic with per-record coverage rows"

echo "--- T-COVERAGE-CHAIN-002: per-record coverage failure not masked (missing) ---"
mutate_record_fixture "$TMPDIR_LOCAL/r2.json" "missing_required.json" 0 "$TMPDIR_LOCAL/r2_missing.json"
make_chain_jsonl "$TMPDIR_LOCAL/chain_missing.jsonl" "$TMPDIR_LOCAL/r1.json" "$TMPDIR_LOCAL/r2_missing.json"
set +e
python3 "$CHAIN" --require-coverage-stamp "$TMPDIR_LOCAL/chain_missing.jsonl" > "$TMPDIR_LOCAL/miss1.out" 2>&1
MRC1=$?
python3 "$CHAIN" --require-coverage-stamp "$TMPDIR_LOCAL/chain_missing.jsonl" > "$TMPDIR_LOCAL/miss2.out" 2>&1
MRC2=$?
set -e
[[ "$MRC1" == "1" && "$MRC2" == "1" ]] || { echo "FAIL: expected rc=1 for missing stamp got rc1=$MRC1 rc2=$MRC2"; exit 1; }
M1="$(sha256_file "$TMPDIR_LOCAL/miss1.out")"
M2="$(sha256_file "$TMPDIR_LOCAL/miss2.out")"
[[ "$M1" == "$M2" ]] || { echo "FAIL: missing failure output nondeterministic"; exit 1; }
OUT_M="$(cat "$TMPDIR_LOCAL/miss1.out")"
assert_contains "missing failure line" "$OUT_M" "FAIL: line 2: COVERAGE_STAMP_MISSING"
echo "PASS: missing coverage failure deterministic and line-local"

echo "--- T-COVERAGE-CHAIN-003: malformed coverage failure not masked (per-record reason) ---"
mutate_record_fixture "$TMPDIR_LOCAL/r2.json" "wrong_type_fields.json" 1 "$TMPDIR_LOCAL/r2_bad.json"
make_chain_jsonl "$TMPDIR_LOCAL/chain_bad.jsonl" "$TMPDIR_LOCAL/r1.json" "$TMPDIR_LOCAL/r2_bad.json"
set +e
python3 "$CHAIN" --require-coverage-stamp "$TMPDIR_LOCAL/chain_bad.jsonl" > "$TMPDIR_LOCAL/bad1.out" 2>&1
BRC1=$?
python3 "$CHAIN" --require-coverage-stamp "$TMPDIR_LOCAL/chain_bad.jsonl" > "$TMPDIR_LOCAL/bad2.out" 2>&1
BRC2=$?
set -e
[[ "$BRC1" == "1" && "$BRC2" == "1" ]] || { echo "FAIL: expected rc=1 for malformed stamp got rc1=$BRC1 rc2=$BRC2"; exit 1; }
B1="$(sha256_file "$TMPDIR_LOCAL/bad1.out")"
B2="$(sha256_file "$TMPDIR_LOCAL/bad2.out")"
[[ "$B1" == "$B2" ]] || { echo "FAIL: malformed failure output nondeterministic"; exit 1; }
OUT_B="$(cat "$TMPDIR_LOCAL/bad1.out")"
assert_contains "malformed failure line" "$OUT_B" "FAIL: line 2: COVERAGE_STAMP_MALFORMED"
echo "PASS: malformed coverage failure deterministic and line-local"

echo "COVERAGE_CHAIN_OK_SHA256_RUN1=$OK1"
echo "COVERAGE_CHAIN_OK_SHA256_RUN2=$OK2"
echo "COVERAGE_CHAIN_MISSING_SHA256_RUN1=$M1"
echo "COVERAGE_CHAIN_MISSING_SHA256_RUN2=$M2"
echo "COVERAGE_CHAIN_MALFORMED_SHA256_RUN1=$B1"
echo "COVERAGE_CHAIN_MALFORMED_SHA256_RUN2=$B2"
echo "Summary: coverage stamp verify-chain contract checks complete"
