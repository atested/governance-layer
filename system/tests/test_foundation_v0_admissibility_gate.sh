#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

make_bundle_core() {
  local dir="$1"
  mkdir -p "$dir"
  cat > "$dir/record.json" <<'JSON'
{"record":"ok"}
JSON
  cat > "$dir/manifest.json" <<'JSON'
{"proof_packet_version":"proof_packet_v1","files":{"record.json":{"sha256":"dummy"}}}
JSON
  tar -cf "$dir/proof_packet.tar" -C "$dir" manifest.json record.json
  python3 - <<'PY' "$dir/proof_packet.tar" > "$dir/proof_packet.sha256"
import hashlib,sys
p=sys.argv[1]
print(hashlib.sha256(open(p,'rb').read()).hexdigest()+"  proof_packet.tar")
PY
  cat > "$dir/proof_packet_verify_summary.json" <<'JSON'
{"report_version":"proof_packet_verify_summary_v1","result":"PASS"}
JSON
  cat > "$dir/release_gate_log.txt" <<'TXT'
profile=dev
result=PASS
TXT
  cat > "$dir/versions.txt" <<'TXT'
proof_packet=proof_packet_v1
summary=proof_packet_verify_summary_v1
TXT
}

make_ledger_artifacts() {
  local dir="$1"; local coverage_json="$2"; shift 2
  cat > "$dir/decision.json" <<'JSON'
{"decision":"allow","id":"d-1"}
JSON
  cat > "$dir/rules.json" <<'JSON'
{"policy":"v0","rules":["A"]}
JSON
  printf 'input-data\n' > "$dir/input.bin"
  printf '%s\n' "$coverage_json" > "$dir/coverage_stamp.json"
  python3 - <<'PY' "$dir/coverage_stamp.json" > "$dir/stamp.hash"
import hashlib,json,sys
obj=json.load(open(sys.argv[1]))
s=json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False)
print('sha256:'+hashlib.sha256(s.encode()).hexdigest())
PY
  stamp_hash="$(cat "$dir/stamp.hash")"
  cat > "$dir/proof_manifest.json" <<JSON
{"coverage_stamp_ref":"$stamp_hash","manifest_version":"v0"}
JSON
}

append_entry() {
  local dir="$1"; shift
  python3 scripts/foundation_v0_process_ledger.py append \
    --ledger "$dir/ledger.jsonl" \
    --operation-id "$1" \
    --capability-surface "$2" \
    ${3:+--capability-surface "$3"} \
    --decision-record "$dir/decision.json" \
    --proof-bundle-manifest "$dir/proof_manifest.json" \
    --rules-snapshot "$dir/rules.json" \
    --input-file "$dir/input.bin" >/dev/null
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# 1) PASS case
b1="$tmp/pass"
make_bundle_core "$b1"
make_ledger_artifacts "$b1" '{"coverage_stamp_version":"coverage_stamp_v1","generated_by":"test","generated_from":["sourceA"],"overall_status":"complete","surfaces":[{"surface_id":"filesystem","capability_surface":"filesystem","coverage":{"observation":true,"enforcement":true,"provenance":true},"evidence_sources":["ev1"]}]}'
append_entry "$b1" "11111111-1111-4111-8111-111111111111" filesystem
out1="$(system/scripts/foundation-v0-admissibility-gate.sh --proof-bundle-dir "$b1" --ledger-path "$b1/ledger.jsonl")"
printf '%s\n' "$out1" | rg '^ADMISSIBLE=YES$' >/dev/null
printf '%s\n' "$out1" | rg '^STOP_REQUIRED=NO$' >/dev/null
printf '%s\n' "$out1" | rg '^REASON_CODE=RC_OK$' >/dev/null

# 2) NON_ADMISSIBLE coverage mismatch
b2="$tmp/nonad"
make_bundle_core "$b2"
make_ledger_artifacts "$b2" '{"coverage_stamp_version":"coverage_stamp_v1","generated_by":"test","generated_from":["sourceA"],"overall_status":"complete","surfaces":[{"surface_id":"filesystem","capability_surface":"filesystem","coverage":{"observation":true,"enforcement":true,"provenance":true},"evidence_sources":["ev1"]}]}'
append_entry "$b2" "22222222-2222-4222-8222-222222222222" filesystem shell
set +e
system/scripts/foundation-v0-admissibility-gate.sh --proof-bundle-dir "$b2" --ledger-path "$b2/ledger.jsonl" > "$tmp/nonad.out" 2>&1
rc2=$?
set -e
[[ "$rc2" -eq 1 ]]
rg '^ADMISSIBLE=NO$' "$tmp/nonad.out" >/dev/null
rg '^STOP_REQUIRED=NO$' "$tmp/nonad.out" >/dev/null
rg '^REASON_CODE=SILENT_SURFACES$' "$tmp/nonad.out" >/dev/null

# 3) STOP case chain break
b3="$tmp/stop"
make_bundle_core "$b3"
make_ledger_artifacts "$b3" '{"coverage_stamp_version":"coverage_stamp_v1","generated_by":"test","generated_from":["sourceA"],"overall_status":"complete","surfaces":[{"surface_id":"filesystem","capability_surface":"filesystem","coverage":{"observation":true,"enforcement":true,"provenance":true},"evidence_sources":["ev1"]}]}'
append_entry "$b3" "33333333-3333-4333-8333-333333333333" filesystem
python3 - <<'PY' "$b3/ledger.jsonl"
import json,sys
p=sys.argv[1]
obj=json.loads(open(p).read().splitlines()[0])
obj['operation_id']='44444444-4444-4444-8444-444444444444'
open(p,'w').write(json.dumps(obj,sort_keys=True,separators=(',',':'))+'\n')
PY
set +e
system/scripts/foundation-v0-admissibility-gate.sh --proof-bundle-dir "$b3" --ledger-path "$b3/ledger.jsonl" > "$tmp/stop.out" 2>&1
rc3=$?
set -e
[[ "$rc3" -eq 2 ]]
rg '^ADMISSIBLE=NO$' "$tmp/stop.out" >/dev/null
rg '^STOP_REQUIRED=YES$' "$tmp/stop.out" >/dev/null
rg '^REASON_CODE=ENTRY_HASH_MISMATCH$' "$tmp/stop.out" >/dev/null

# 4) HASH_NOT_FOUND NON_ADMISSIBLE
b4="$tmp/missing"
make_bundle_core "$b4"
make_ledger_artifacts "$b4" '{"coverage_stamp_version":"coverage_stamp_v1","generated_by":"test","generated_from":["sourceA"],"overall_status":"complete","surfaces":[{"surface_id":"filesystem","capability_surface":"filesystem","coverage":{"observation":true,"enforcement":true,"provenance":true},"evidence_sources":["ev1"]}]}'
append_entry "$b4" "55555555-5555-4555-8555-555555555555" filesystem
rm -f "$b4/input.bin"
set +e
system/scripts/foundation-v0-admissibility-gate.sh --proof-bundle-dir "$b4" --ledger-path "$b4/ledger.jsonl" > "$tmp/missing.out" 2>&1
rc4=$?
set -e
[[ "$rc4" -eq 1 ]]
rg '^ADMISSIBLE=NO$' "$tmp/missing.out" >/dev/null
rg '^STOP_REQUIRED=NO$' "$tmp/missing.out" >/dev/null
rg '^REASON_CODE=HASH_NOT_FOUND$' "$tmp/missing.out" >/dev/null

echo "PASS test_foundation_v0_admissibility_gate"
