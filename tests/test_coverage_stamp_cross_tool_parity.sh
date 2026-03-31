#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
VERIFY="$ROOT/scripts/verify-record.py"
CHAIN="$ROOT/scripts/verify-chain.py"
REPLAY="$ROOT/scripts/replay-record.py"
FIX="$ROOT/tests/fixtures/coverage_stamp"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/coverage-stamp-parity.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
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
  'intent':{'goal':'Coverage stamp parity regression','constraints':{},'requested_action':'FS_READ','inputs':[],'expected_outputs':[{'ref':'file:path','value':str(root/'capabilities'/'capability-registry.json')}]},
}
if include_stamp:
    intent['coverage_stamp']=json.loads((fix/fixture_name).read_text(encoding='utf-8'))
out.write_text(json.dumps(intent, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
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
include_stamp=(sys.argv[5] == '1')
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

extract_reason_from_text() {
  python3 - <<'PY' "$1"
import re,sys
text=open(sys.argv[1], 'r', encoding='utf-8').read()
m=re.search(r'(COVERAGE_STAMP_[A-Z_]+)', text)
print(m.group(1) if m else '')
PY
}

extract_policy_reason() {
  python3 - <<'PY' "$1"
import json,sys
obj=json.loads(open(sys.argv[1], 'r', encoding='utf-8').read())
print(obj.get('coverage_stamp_summary', {}).get('reason_code', ''))
PY
}

expected_case() {
  local fixture="$1"
  case "$fixture" in
    complete_v1.json|minimal_valid_required_only.json|multiple_surfaces_valid.json)
      echo "0 COVERAGE_STAMP_OK 0 COVERAGE_STAMP_OK 0 COVERAGE_STAMP_OK 0 COVERAGE_STAMP_OK 1" ;;
    partial_required.json|mixed_required_optional_partial.json)
      echo "0 COVERAGE_STAMP_PARTIAL 1 COVERAGE_STAMP_PARTIAL 1 COVERAGE_STAMP_PARTIAL 1 COVERAGE_STAMP_PARTIAL 1" ;;
    invalid_enum_value.json)
      echo "0 COVERAGE_STAMP_SURFACE_UNKNOWN 1 COVERAGE_STAMP_SURFACE_UNKNOWN 1 COVERAGE_STAMP_SURFACE_UNKNOWN 1 COVERAGE_STAMP_SURFACE_UNKNOWN 1" ;;
    order_invalid.json|non_canonical_surface_order.json|deep_order_invalid.json|generated_from_unsorted.json|evidence_sources_unsorted.json)
      echo "0 COVERAGE_STAMP_ORDER_INVALID 1 COVERAGE_STAMP_ORDER_INVALID 1 COVERAGE_STAMP_ORDER_INVALID 1 COVERAGE_STAMP_ORDER_INVALID 1" ;;
    unknown_version.json)
      echo "0 COVERAGE_STAMP_VERSION_UNSUPPORTED 1 COVERAGE_STAMP_VERSION_UNSUPPORTED 1 COVERAGE_STAMP_VERSION_UNSUPPORTED 1 COVERAGE_STAMP_VERSION_UNSUPPORTED 1" ;;
    missing_required.json|optional_absent.json)
      echo "0 COVERAGE_STAMP_MISSING 1 COVERAGE_STAMP_MISSING 1 COVERAGE_STAMP_MISSING 1 COVERAGE_STAMP_MISSING 0" ;;
    *)
      echo "0 COVERAGE_STAMP_MALFORMED 1 COVERAGE_STAMP_MALFORMED 1 COVERAGE_STAMP_MALFORMED 1 COVERAGE_STAMP_MALFORMED 1" ;;
  esac
}

run_case() {
  local fixture="$1"
  read -r p_rc exp_reason v_rc v_reason c_rc c_reason r_rc r_reason include_stamp < <(expected_case "$fixture")

  build_intent "$fixture" "$include_stamp" "$TMPDIR_LOCAL/$fixture.intent.json"

  set +e
  GOV_COVERAGE_STAMP_REQUIRED=1 python3 "$EVAL" "$TMPDIR_LOCAL/$fixture.intent.json" > "$TMPDIR_LOCAL/$fixture.policy.out" 2>&1
  policy_rc=$?
  set -e
  [[ "$policy_rc" == "$p_rc" ]] || { echo "FAIL: fixture=$fixture policy rc expected=$p_rc actual=$policy_rc"; exit 1; }
  policy_reason="$(extract_policy_reason "$TMPDIR_LOCAL/$fixture.policy.out")"
  [[ "$policy_reason" == "$exp_reason" ]] || { echo "FAIL: fixture=$fixture policy reason expected=$exp_reason actual=$policy_reason"; exit 1; }

  # Mutate the policy-emitted record from this exact fixture intent so replay request bytes stay aligned.
  mutate_record_fixture "$TMPDIR_LOCAL/$fixture.policy.out" "$fixture" "$include_stamp" "$TMPDIR_LOCAL/$fixture.record.json"

  set +e
  GOV_COVERAGE_STAMP_REQUIRED=1 python3 "$VERIFY" "$TMPDIR_LOCAL/$fixture.record.json" > "$TMPDIR_LOCAL/$fixture.verify.out" 2>&1
  verify_rc=$?
  python3 - <<'PY' "$TMPDIR_LOCAL/$fixture.record.json" "$TMPDIR_LOCAL/$fixture.chain.jsonl"
import json,sys,pathlib
rec=pathlib.Path(sys.argv[1])
out=pathlib.Path(sys.argv[2])
doc=json.loads(rec.read_text(encoding='utf-8'))
out.write_text(json.dumps(doc, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
PY
  python3 "$CHAIN" --require-coverage-stamp "$TMPDIR_LOCAL/$fixture.chain.jsonl" > "$TMPDIR_LOCAL/$fixture.chain.out" 2>&1
  chain_rc=$?
  python3 "$REPLAY" --require-coverage-stamp "$TMPDIR_LOCAL/$fixture.record.json" > "$TMPDIR_LOCAL/$fixture.replay.out" 2>&1
  replay_rc=$?
  set -e

  [[ "$verify_rc" == "$v_rc" ]] || { echo "FAIL: fixture=$fixture verify rc expected=$v_rc actual=$verify_rc"; exit 1; }
  [[ "$chain_rc" == "$c_rc" ]] || { echo "FAIL: fixture=$fixture chain rc expected=$c_rc actual=$chain_rc"; exit 1; }
  [[ "$replay_rc" == "$r_rc" ]] || { echo "FAIL: fixture=$fixture replay rc expected=$r_rc actual=$replay_rc"; exit 1; }

  verify_reason="$(extract_reason_from_text "$TMPDIR_LOCAL/$fixture.verify.out")"
  chain_reason="$(extract_reason_from_text "$TMPDIR_LOCAL/$fixture.chain.out")"
  replay_reason="$(extract_reason_from_text "$TMPDIR_LOCAL/$fixture.replay.out")"

  [[ "$verify_reason" == "$v_reason" ]] || { echo "FAIL: fixture=$fixture verify reason expected=$v_reason actual=$verify_reason"; exit 1; }
  [[ "$chain_reason" == "$c_reason" ]] || { echo "FAIL: fixture=$fixture chain reason expected=$c_reason actual=$chain_reason"; exit 1; }
  [[ "$replay_reason" == "$r_reason" ]] || { echo "FAIL: fixture=$fixture replay reason expected=$r_reason actual=$replay_reason"; exit 1; }

  python3 - <<'PY' "$TMPDIR_LOCAL/$fixture.policy.out" "$TMPDIR_LOCAL/$fixture.verify.out" "$TMPDIR_LOCAL/$fixture.chain.out" "$TMPDIR_LOCAL/$fixture.replay.out" "$TMPDIR_LOCAL/$fixture.parity.out"
import pathlib, re, sys
inp=[pathlib.Path(p) for p in sys.argv[1:5]]
out=pathlib.Path(sys.argv[5])
text=[]
for p in inp:
    s=p.read_text(encoding='utf-8')
    s=re.sub(r'/tmp/[^\s,)]*', '<tmp>', s)
    text.append(s)
out.write_text('\n---\n'.join(text), encoding='utf-8')
PY

  echo "PARITY fixture=$fixture policy_rc=$policy_rc policy_reason=$policy_reason verify_rc=$verify_rc verify_reason=$verify_reason chain_rc=$chain_rc chain_reason=$chain_reason replay_rc=$replay_rc replay_reason=$replay_reason"
}

echo "--- T-COVERAGE-PARITY-001: cross-tool parity for coverage stamp fixtures ---"
for fixture in $(cd "$FIX" && ls *.json | LC_ALL=C sort); do
  run_case "$fixture"
done

echo "Summary: cross-tool parity checks complete"
