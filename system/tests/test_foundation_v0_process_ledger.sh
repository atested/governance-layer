#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LEDGER="$ROOT/scripts/foundation_v0_process_ledger.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

write_json() {
  local path="$1"
  local body="$2"
  printf '%s\n' "$body" > "$path"
}

hash_canon_json_file() {
  python3 - "$1" <<'PY'
import hashlib, json, pathlib, sys
p = pathlib.Path(sys.argv[1])
obj = json.loads(p.read_text(encoding='utf-8'))
s = json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
print('sha256:' + hashlib.sha256(s.encode('utf-8')).hexdigest())
PY
}

setup_artifacts() {
  local dir="$1"
  mkdir -p "$dir/artifacts"
  write_json "$dir/artifacts/decision.json" '{"decision":"allow","id":"d-001"}'
  write_json "$dir/artifacts/rules.json" '{"policy":"v0","rules":["A","B"]}'
  printf 'input-bytes\n' > "$dir/artifacts/input.bin"
  write_json "$dir/artifacts/coverage_stamp.json" '{"coverage_stamp_version":"coverage_stamp_v1","generated_by":"test","generated_from":["sourceA"],"overall_status":"complete","surfaces":[{"surface_id":"filesystem","capability_surface":"filesystem","coverage":{"observation":true,"enforcement":true,"provenance":true},"evidence_sources":["ev1"]},{"surface_id":"shell","capability_surface":"shell","coverage":{"observation":true,"enforcement":true,"provenance":true},"evidence_sources":["ev2"]}]}'
  local stamp_hash
  stamp_hash="$(hash_canon_json_file "$dir/artifacts/coverage_stamp.json")"
  write_json "$dir/artifacts/proof_manifest.json" "{\"coverage_stamp_ref\":\"$stamp_hash\",\"manifest_version\":\"v0\"}"
}

# Test 1: deterministic entry hash
setup_artifacts "$TMP/t1"
python3 "$LEDGER" append \
  --ledger "$TMP/t1/ledger.jsonl" \
  --operation-id "11111111-1111-4111-8111-111111111111" \
  --capability-surface filesystem \
  --capability-surface shell \
  --decision-record "$TMP/t1/artifacts/decision.json" \
  --proof-bundle-manifest "$TMP/t1/artifacts/proof_manifest.json" \
  --rules-snapshot "$TMP/t1/artifacts/rules.json" \
  --input-file "$TMP/t1/artifacts/input.bin" \
  --wall-clock-ts "2026-03-02T00:00:00Z" \
  --host-id "host-fixed" > "$TMP/t1/append1.out"
python3 "$LEDGER" append \
  --ledger "$TMP/t1/ledger_b.jsonl" \
  --operation-id "11111111-1111-4111-8111-111111111111" \
  --capability-surface filesystem \
  --capability-surface shell \
  --decision-record "$TMP/t1/artifacts/decision.json" \
  --proof-bundle-manifest "$TMP/t1/artifacts/proof_manifest.json" \
  --rules-snapshot "$TMP/t1/artifacts/rules.json" \
  --input-file "$TMP/t1/artifacts/input.bin" \
  --wall-clock-ts "2026-03-02T00:00:00Z" \
  --host-id "host-fixed" > "$TMP/t1/append2.out"
E1=$(python3 -c 'import json,sys; print(json.loads(open(sys.argv[1]).readline())["entry_hash"])' "$TMP/t1/ledger.jsonl")
E2=$(python3 -c 'import json,sys; print(json.loads(open(sys.argv[1]).readline())["entry_hash"])' "$TMP/t1/ledger_b.jsonl")
[[ "$E1" == "$E2" ]] || { echo "FAIL TEST1 deterministic entry hash"; exit 1; }

echo "PASS TEST1 deterministic_entry_hash"

# Test 2a: tamper ENTRY_HASH_MISMATCH
cp "$TMP/t1/ledger.jsonl" "$TMP/t2_mismatch.jsonl"
python3 - "$TMP/t2_mismatch.jsonl" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
obj = json.loads(p.read_text().splitlines()[0])
obj['operation_id'] = '22222222-2222-4222-8222-222222222222'
p.write_text(json.dumps(obj, sort_keys=True, separators=(',', ':')) + '\n')
PY
set +e
python3 "$LEDGER" verify --ledger "$TMP/t2_mismatch.jsonl" --artifact-dir "$TMP/t1/artifacts" > "$TMP/t2_mismatch.out" 2>&1
rc_m=$?
set -e
[[ "$rc_m" -ne 0 ]]
rg '^ENTRY_HASH_MISMATCH$' "$TMP/t2_mismatch.out" >/dev/null
echo "PASS TEST2A entry_hash_mismatch"

# Test 2b: tamper CHAIN_BREAK
setup_artifacts "$TMP/t2b"
python3 "$LEDGER" append --ledger "$TMP/t2b/ledger.jsonl" --operation-id "33333333-3333-4333-8333-333333333333" --capability-surface filesystem --decision-record "$TMP/t2b/artifacts/decision.json" --proof-bundle-manifest "$TMP/t2b/artifacts/proof_manifest.json" --rules-snapshot "$TMP/t2b/artifacts/rules.json" --input-file "$TMP/t2b/artifacts/input.bin" >/dev/null
python3 "$LEDGER" append --ledger "$TMP/t2b/ledger.jsonl" --operation-id "44444444-4444-4444-8444-444444444444" --capability-surface filesystem --decision-record "$TMP/t2b/artifacts/decision.json" --proof-bundle-manifest "$TMP/t2b/artifacts/proof_manifest.json" --rules-snapshot "$TMP/t2b/artifacts/rules.json" --input-file "$TMP/t2b/artifacts/input.bin" >/dev/null
python3 - "$TMP/t2b/ledger.jsonl" <<'PY'
import hashlib, json, pathlib, sys
p = pathlib.Path(sys.argv[1])
lines = [json.loads(x) for x in p.read_text().splitlines()]
lines[1]['prev_entry_hash'] = 'sha256:' + 'f'*64

canonical = {
    "append_seq": lines[1]["append_seq"],
    "capability_surfaces": sorted(lines[1]["capability_surfaces"]),
    "decision_record_ref": lines[1]["decision_record_ref"],
    "input_artifact_refs": sorted(lines[1]["input_artifact_refs"], key=lambda x: (x["type"], x["hash"])),
    "operation_id": lines[1]["operation_id"],
    "prev_entry_hash": lines[1]["prev_entry_hash"],
    "proof_bundle_ref": lines[1]["proof_bundle_ref"],
    "rules_ref": lines[1]["rules_ref"],
}
blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
lines[1]["entry_hash"] = "sha256:" + hashlib.sha256(blob).hexdigest()

p.write_text('\n'.join(json.dumps(x, sort_keys=True, separators=(',', ':')) for x in lines) + '\n')
PY
set +e
python3 "$LEDGER" verify --ledger "$TMP/t2b/ledger.jsonl" --artifact-dir "$TMP/t2b/artifacts" > "$TMP/t2b.out" 2>&1
rc_c=$?
set -e
[[ "$rc_c" -ne 0 ]]
rg '^CHAIN_BREAK$' "$TMP/t2b.out" >/dev/null
echo "PASS TEST2B chain_break"

# Test 3: missing artifact => HASH_NOT_FOUND NON_ADMISSIBLE
setup_artifacts "$TMP/t3"
python3 "$LEDGER" append --ledger "$TMP/t3/ledger.jsonl" --operation-id "55555555-5555-4555-8555-555555555555" --capability-surface filesystem --decision-record "$TMP/t3/artifacts/decision.json" --proof-bundle-manifest "$TMP/t3/artifacts/proof_manifest.json" --rules-snapshot "$TMP/t3/artifacts/rules.json" --input-file "$TMP/t3/artifacts/input.bin" >/dev/null
rm -f "$TMP/t3/artifacts/input.bin"
python3 "$LEDGER" verify --ledger "$TMP/t3/ledger.jsonl" --artifact-dir "$TMP/t3/artifacts" --report-out "$TMP/t3/report.json" --write-ledger-metadata > "$TMP/t3.out"
rg '^VERIFY_STATUS=NON_ADMISSIBLE$' "$TMP/t3.out" >/dev/null
python3 - "$TMP/t3/report.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
codes = set(r['entries'][0]['failure_codes'])
assert 'HASH_NOT_FOUND' in codes
print('PASS TEST3 missing_artifact')
PY

# Test 4: no-refetch enforcement
rg -n 'import requests|urllib|http\.client|socket' "$LEDGER" >/dev/null && { echo "FAIL TEST4 no_refetch"; exit 1; } || true
python3 "$LEDGER" verify --ledger "$TMP/t3/ledger.jsonl" --artifact-dir "$TMP/t3/artifacts" --report-out "$TMP/t3/report2.json" > "$TMP/t4.out"
rg '^VERIFY_STATUS=NON_ADMISSIBLE$' "$TMP/t4.out" >/dev/null
echo "PASS TEST4 no_refetch_enforcement"

# Test 5: coverage subset mismatch => SILENT_SURFACES
setup_artifacts "$TMP/t5"
write_json "$TMP/t5/artifacts/coverage_stamp.json" '{"coverage_stamp_version":"coverage_stamp_v1","generated_by":"test","generated_from":["sourceA"],"overall_status":"complete","surfaces":[{"surface_id":"filesystem","capability_surface":"filesystem","coverage":{"observation":true,"enforcement":true,"provenance":true},"evidence_sources":["ev1"]}]}'
stamp_hash_t5="$(hash_canon_json_file "$TMP/t5/artifacts/coverage_stamp.json")"
write_json "$TMP/t5/artifacts/proof_manifest.json" "{\"coverage_stamp_ref\":\"$stamp_hash_t5\",\"manifest_version\":\"v0\"}"
python3 "$LEDGER" append --ledger "$TMP/t5/ledger.jsonl" --operation-id "66666666-6666-4666-8666-666666666666" --capability-surface filesystem --capability-surface shell --decision-record "$TMP/t5/artifacts/decision.json" --proof-bundle-manifest "$TMP/t5/artifacts/proof_manifest.json" --rules-snapshot "$TMP/t5/artifacts/rules.json" --input-file "$TMP/t5/artifacts/input.bin" >/dev/null
python3 "$LEDGER" verify --ledger "$TMP/t5/ledger.jsonl" --artifact-dir "$TMP/t5/artifacts" --report-out "$TMP/t5/report.json" > "$TMP/t5.out"
rg '^VERIFY_STATUS=NON_ADMISSIBLE$' "$TMP/t5.out" >/dev/null
python3 - "$TMP/t5/report.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
codes = set(r['entries'][0]['failure_codes'])
assert 'SILENT_SURFACES' in codes
print('PASS TEST5 coverage_subset_mismatch')
PY

echo "PASS ALL foundation_v0_process_ledger"
