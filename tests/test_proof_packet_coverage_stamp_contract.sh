#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKER="$ROOT/scripts/proof-packet.py"
EVAL="$ROOT/scripts/policy-eval.py"
FIX="$ROOT/tests/fixtures/coverage_stamp"
ABFIX="$ROOT/tests/fixtures/attestation_bundle/sample"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/proof-packet-coverage-contract.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

build_intent() {
  local fixture_name="$1"
  local out="$2"
  python3 - <<'PY' "$ROOT" "$FIX" "$fixture_name" "$out"
import json,sys,pathlib
root=pathlib.Path(sys.argv[1])
fix=pathlib.Path(sys.argv[2])
fixture_name=sys.argv[3]
out=pathlib.Path(sys.argv[4])
intent={
  'tool':'FS_READ',
  'args':{'path':str(root/'capabilities'/'capability-registry.json'),'max_bytes':4096,'offset':0,'as_text':True},
  'intent':{'goal':'Proof packet coverage contract','constraints':{},'requested_action':'FS_READ','inputs':[],'expected_outputs':[{'ref':'file:path','value':str(root/'capabilities'/'capability-registry.json')}]},
  'coverage_stamp': json.loads((fix/fixture_name).read_text(encoding='utf-8')),
}
out.write_text(json.dumps(intent, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
PY
}

echo "--- T-PROOF-COVERAGE-001: deterministic inclusion of coverage stamp in manifest + summary ---"
build_intent "multiple_surfaces_valid.json" "$TMPDIR_LOCAL/intent.json"
GOV_COVERAGE_STAMP_REQUIRED=1 python3 "$EVAL" "$TMPDIR_LOCAL/intent.json" > "$TMPDIR_LOCAL/record.json"
cp -R "$ABFIX/artifacts" "$TMPDIR_LOCAL/artifacts"
cp "$ABFIX/replay_audit_report.json" "$TMPDIR_LOCAL/replay_audit_report.json"
python3 "$PACKER" pack --record "$TMPDIR_LOCAL/record.json" --artifacts-dir "$TMPDIR_LOCAL/artifacts" --replay-audit-report "$TMPDIR_LOCAL/replay_audit_report.json" --out "$TMPDIR_LOCAL/p1.tar" > "$TMPDIR_LOCAL/p1.out"
python3 "$PACKER" pack --record "$TMPDIR_LOCAL/record.json" --artifacts-dir "$TMPDIR_LOCAL/artifacts" --replay-audit-report "$TMPDIR_LOCAL/replay_audit_report.json" --out "$TMPDIR_LOCAL/p2.tar" > "$TMPDIR_LOCAL/p2.out"
python3 "$PACKER" verify --bundle "$TMPDIR_LOCAL/p1.tar" --summary-json "$TMPDIR_LOCAL/s1.json" > "$TMPDIR_LOCAL/v1.out"
python3 "$PACKER" verify --bundle "$TMPDIR_LOCAL/p2.tar" --summary-json "$TMPDIR_LOCAL/s2.json" > "$TMPDIR_LOCAL/v2.out"

P1="$(sha256_file "$TMPDIR_LOCAL/p1.tar")"
P2="$(sha256_file "$TMPDIR_LOCAL/p2.tar")"
S1="$(sha256_file "$TMPDIR_LOCAL/s1.json")"
S2="$(sha256_file "$TMPDIR_LOCAL/s2.json")"
[[ "$P1" == "$P2" ]] || { echo "FAIL: proof packet bytes nondeterministic"; exit 1; }
[[ "$S1" == "$S2" ]] || { echo "FAIL: verify summary bytes nondeterministic"; exit 1; }

python3 - <<'PY' "$TMPDIR_LOCAL/p1.tar" "$TMPDIR_LOCAL/s1.json"
import json,sys,tarfile
packet, summary = sys.argv[1], sys.argv[2]
with tarfile.open(packet, 'r:') as tf:
    manifest = json.load(tf.extractfile('manifest.json'))
assert 'coverage_stamp' in manifest
assert manifest['coverage_stamp']['coverage_stamp_version'] == 'coverage_stamp_v1'
base_required = {'proof_packet_version','hash_algo','files','source_summary'}
assert base_required.issubset(set(manifest.keys()))
summary_doc = json.load(open(summary, 'r', encoding='utf-8'))
assert 'coverage_stamp_summary' in summary_doc
assert summary_doc['coverage_stamp_summary']['coverage_stamp_version'] == 'coverage_stamp_v1'
print('PASS: proof packet includes coverage stamp additively in manifest and summary')
PY

echo "--- T-PROOF-COVERAGE-002: malformed coverage stamp fails closed during pack ---"
python3 - <<'PY' "$TMPDIR_LOCAL/record.json" "$FIX/wrong_type_fields.json" "$TMPDIR_LOCAL/record_bad.json"
import json,sys,pathlib
rec=pathlib.Path(sys.argv[1])
stamp=pathlib.Path(sys.argv[2])
out=pathlib.Path(sys.argv[3])
doc=json.loads(rec.read_text(encoding='utf-8'))
doc['coverage_stamp']=json.loads(stamp.read_text(encoding='utf-8'))
out.write_text(json.dumps(doc, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
PY
set +e
python3 "$PACKER" pack --record "$TMPDIR_LOCAL/record_bad.json" --artifacts-dir "$TMPDIR_LOCAL/artifacts" --replay-audit-report "$TMPDIR_LOCAL/replay_audit_report.json" --out "$TMPDIR_LOCAL/bad1.tar" > "$TMPDIR_LOCAL/bad1.out" 2>&1
RC1=$?
python3 "$PACKER" pack --record "$TMPDIR_LOCAL/record_bad.json" --artifacts-dir "$TMPDIR_LOCAL/artifacts" --replay-audit-report "$TMPDIR_LOCAL/replay_audit_report.json" --out "$TMPDIR_LOCAL/bad2.tar" > "$TMPDIR_LOCAL/bad2.out" 2>&1
RC2=$?
set -e
[[ "$RC1" == "2" && "$RC2" == "2" ]] || { echo "FAIL: malformed coverage stamp expected rc=2 got rc1=$RC1 rc2=$RC2"; exit 1; }
B1="$(sha256_file "$TMPDIR_LOCAL/bad1.out")"
B2="$(sha256_file "$TMPDIR_LOCAL/bad2.out")"
[[ "$B1" == "$B2" ]] || { echo "FAIL: malformed coverage pack output nondeterministic"; exit 1; }
grep -q "record coverage_stamp invalid: COVERAGE_STAMP_MALFORMED" "$TMPDIR_LOCAL/bad1.out" || { echo "FAIL: malformed failure reason marker missing"; exit 1; }

echo "PASS: proof-packet and summary digests match within invocation"
echo "PASS: malformed coverage rejection output stable within invocation"
echo "Summary: proof-packet coverage inclusion contract checks complete"
