#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
VERIFY="$ROOT/scripts/verify-record.py"
PACKER="$ROOT/scripts/proof-packet.py"
FIX="$ROOT/tests/fixtures/coverage_stamp"
ABFIX="$ROOT/tests/fixtures/attestation_bundle/sample"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/coverage-stamp-ordering.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

build_intent() {
  local out="$1"
  python3 - <<'PY' "$ROOT" "$FIX/complete_v1.json" "$out"
import json,sys,pathlib
root=pathlib.Path(sys.argv[1])
stamp=json.loads(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8'))
out=pathlib.Path(sys.argv[3])
intent={
  'tool':'FS_READ',
  'args':{'path':str(root/'capabilities'/'capability-registry.json'),'max_bytes':4096,'offset':0,'as_text':True},
  'intent':{'goal':'Coverage stamp ordering regression','constraints':{},'requested_action':'FS_READ','inputs':[],'expected_outputs':[{'ref':'file:path','value':str(root/'capabilities'/'capability-registry.json')}]},
  'coverage_stamp': stamp,
}
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

extract_reason() {
  python3 - <<'PY' "$1"
import re,sys
text=open(sys.argv[1], 'r', encoding='utf-8').read()
m=re.search(r'(COVERAGE_STAMP_[A-Z_]+)', text)
print(m.group(1) if m else '')
PY
}

expected_for_fixture() {
  local fixture="$1"
  case "$fixture" in
    complete_v1.json|minimal_valid_required_only.json|multiple_surfaces_valid.json)
      echo "0 COVERAGE_STAMP_OK 1" ;;
    partial_required.json|mixed_required_optional_partial.json)
      echo "1 COVERAGE_STAMP_PARTIAL 1" ;;
    invalid_enum_value.json)
      echo "1 COVERAGE_STAMP_SURFACE_UNKNOWN 1" ;;
    order_invalid.json|non_canonical_surface_order.json|deep_order_invalid.json|generated_from_unsorted.json|evidence_sources_unsorted.json)
      echo "1 COVERAGE_STAMP_ORDER_INVALID 1" ;;
    unknown_version.json)
      echo "1 COVERAGE_STAMP_VERSION_UNSUPPORTED 1" ;;
    missing_required.json|optional_absent.json)
      echo "1 COVERAGE_STAMP_MISSING 0" ;;
    *)
      echo "1 COVERAGE_STAMP_MALFORMED 1" ;;
  esac
}

echo "--- T-COVERAGE-ORDER-MATRIX-001: verify-record deterministic matrix across all fixtures ---"
build_intent "$TMPDIR_LOCAL/base.intent.json"
GOV_COVERAGE_STAMP_REQUIRED=1 python3 "$EVAL" "$TMPDIR_LOCAL/base.intent.json" > "$TMPDIR_LOCAL/base.record.json"

while IFS= read -r fixture; do
  read -r expected_rc expected_reason include_stamp < <(expected_for_fixture "$fixture")
  mutate_record_fixture "$TMPDIR_LOCAL/base.record.json" "$fixture" "$include_stamp" "$TMPDIR_LOCAL/$fixture.record.json"

  set +e
  GOV_COVERAGE_STAMP_REQUIRED=1 python3 "$VERIFY" "$TMPDIR_LOCAL/$fixture.record.json" > "$TMPDIR_LOCAL/$fixture.run1.out" 2>&1
  rc1=$?
  GOV_COVERAGE_STAMP_REQUIRED=1 python3 "$VERIFY" "$TMPDIR_LOCAL/$fixture.record.json" > "$TMPDIR_LOCAL/$fixture.run2.out" 2>&1
  rc2=$?
  set -e

  [[ "$rc1" == "$expected_rc" && "$rc2" == "$expected_rc" ]] || {
    echo "FAIL: fixture=$fixture expected_rc=$expected_rc rc1=$rc1 rc2=$rc2"
    exit 1
  }

  local_sha1="$(sha256_file "$TMPDIR_LOCAL/$fixture.run1.out")"
  local_sha2="$(sha256_file "$TMPDIR_LOCAL/$fixture.run2.out")"
  [[ "$local_sha1" == "$local_sha2" ]] || {
    echo "FAIL: fixture=$fixture stdout nondeterministic"
    exit 1
  }

  reason="$(extract_reason "$TMPDIR_LOCAL/$fixture.run1.out")"
  [[ "$reason" == "$expected_reason" ]] || {
    echo "FAIL: fixture=$fixture expected_reason=$expected_reason actual_reason=$reason"
    exit 1
  }

  if [[ "$expected_rc" == "0" ]]; then
    grep -q "Coverage Summary" "$TMPDIR_LOCAL/$fixture.run1.out" || {
      echo "FAIL: fixture=$fixture expected coverage summary on pass"
      exit 1
    }
  fi

  echo "FIXTURE_CHECK fixture=$fixture expected_rc=$expected_rc observed_rc=$rc1 expected_reason=$expected_reason observed_reason=$reason stdout_sha_run1=$local_sha1 stdout_sha_run2=$local_sha2"
done < <(cd "$FIX" && ls *.json | LC_ALL=C sort)

echo "--- T-COVERAGE-ORDER-MATRIX-002: proof-packet coverage inclusion deterministic and additive ---"
mkdir -p "$TMPDIR_LOCAL/artifacts"
cp "$ABFIX/artifacts/request.txt" "$TMPDIR_LOCAL/artifacts/request.txt"
cp "$ABFIX/artifacts/response.txt" "$TMPDIR_LOCAL/artifacts/response.txt"
cp "$ABFIX/replay_audit_report.json" "$TMPDIR_LOCAL/replay_audit_report.json"

# Valid coverage stamp included.
mutate_record_fixture "$TMPDIR_LOCAL/base.record.json" "multiple_surfaces_valid.json" 1 "$TMPDIR_LOCAL/record_packet_ok.json"
python3 "$PACKER" pack --record "$TMPDIR_LOCAL/record_packet_ok.json" --artifacts-dir "$TMPDIR_LOCAL/artifacts" --replay-audit-report "$TMPDIR_LOCAL/replay_audit_report.json" --out "$TMPDIR_LOCAL/packet1.tar" > "$TMPDIR_LOCAL/pack1.out"
python3 "$PACKER" pack --record "$TMPDIR_LOCAL/record_packet_ok.json" --artifacts-dir "$TMPDIR_LOCAL/artifacts" --replay-audit-report "$TMPDIR_LOCAL/replay_audit_report.json" --out "$TMPDIR_LOCAL/packet2.tar" > "$TMPDIR_LOCAL/pack2.out"

PK1="$(sha256_file "$TMPDIR_LOCAL/packet1.tar")"
PK2="$(sha256_file "$TMPDIR_LOCAL/packet2.tar")"
[[ "$PK1" == "$PK2" ]] || { echo "FAIL: proof-packet bytes nondeterministic"; exit 1; }
python3 "$PACKER" verify --bundle "$TMPDIR_LOCAL/packet1.tar" --summary-json "$TMPDIR_LOCAL/summary1.json" > "$TMPDIR_LOCAL/verify1.out"
python3 "$PACKER" verify --bundle "$TMPDIR_LOCAL/packet2.tar" --summary-json "$TMPDIR_LOCAL/summary2.json" > "$TMPDIR_LOCAL/verify2.out"
SJ1="$(sha256_file "$TMPDIR_LOCAL/summary1.json")"
SJ2="$(sha256_file "$TMPDIR_LOCAL/summary2.json")"
[[ "$SJ1" == "$SJ2" ]] || { echo "FAIL: proof-packet summary nondeterministic"; exit 1; }
python3 - <<'PY' "$TMPDIR_LOCAL/packet1.tar" "$TMPDIR_LOCAL/summary1.json"
import json,sys,tarfile
packet,summary = sys.argv[1], sys.argv[2]
with tarfile.open(packet, 'r:') as tf:
    m = json.load(tf.extractfile('manifest.json'))
base_keys = {'proof_packet_version','hash_algo','files','source_summary'}
assert base_keys.issubset(set(m.keys())), sorted(m.keys())
assert 'coverage_stamp' in m
assert m['coverage_stamp']['coverage_stamp_version'] == 'coverage_stamp_v1'
assert m['coverage_stamp']['surfaces'] == sorted(m['coverage_stamp']['surfaces'], key=lambda s: ['web','filesystem','shell','routing','model','memory','network','toolchain'].index(s['surface_id']))
s = json.load(open(summary, 'r', encoding='utf-8'))
assert 'coverage_stamp_summary' in s
assert s['coverage_stamp_summary']['coverage_stamp_version'] == 'coverage_stamp_v1'
print('PASS: proof-packet includes deterministic coverage stamp in manifest and summary')
PY

# Malformed coverage stamp fails closed in pack.
mutate_record_fixture "$TMPDIR_LOCAL/base.record.json" "wrong_type_fields.json" 1 "$TMPDIR_LOCAL/record_packet_bad.json"
set +e
python3 "$PACKER" pack --record "$TMPDIR_LOCAL/record_packet_bad.json" --artifacts-dir "$TMPDIR_LOCAL/artifacts" --replay-audit-report "$TMPDIR_LOCAL/replay_audit_report.json" --out "$TMPDIR_LOCAL/bad_packet.tar" > "$TMPDIR_LOCAL/badpack1.out" 2>&1
BRC1=$?
python3 "$PACKER" pack --record "$TMPDIR_LOCAL/record_packet_bad.json" --artifacts-dir "$TMPDIR_LOCAL/artifacts" --replay-audit-report "$TMPDIR_LOCAL/replay_audit_report.json" --out "$TMPDIR_LOCAL/bad_packet2.tar" > "$TMPDIR_LOCAL/badpack2.out" 2>&1
BRC2=$?
set -e
[[ "$BRC1" == "2" && "$BRC2" == "2" ]] || { echo "FAIL: malformed coverage stamp should fail pack rc=2"; exit 1; }
BP1="$(sha256_file "$TMPDIR_LOCAL/badpack1.out")"
BP2="$(sha256_file "$TMPDIR_LOCAL/badpack2.out")"
[[ "$BP1" == "$BP2" ]] || { echo "FAIL: malformed pack output nondeterministic"; exit 1; }
grep -q 'record coverage_stamp invalid: COVERAGE_STAMP_MALFORMED' "$TMPDIR_LOCAL/badpack1.out" || { echo 'FAIL: malformed pack missing stable reason marker'; exit 1; }

echo "PASS: proof-packet byte and summary digests match within invocation"
echo "PASS: malformed proof-packet coverage rejection output stable within invocation"
echo "Summary: coverage stamp canonical ordering checks complete"
