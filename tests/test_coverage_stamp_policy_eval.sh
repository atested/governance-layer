#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
FIX="$ROOT/tests/fixtures/coverage_stamp"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/coverage-stamp-policy-eval.XXXXXX")"
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
root = pathlib.Path(sys.argv[1])
fix = pathlib.Path(sys.argv[2])
fixture_name = sys.argv[3]
include_stamp = sys.argv[4] == "1"
out = pathlib.Path(sys.argv[5])
intent = {
  "tool": "FS_READ",
  "args": {
    "path": str(root / "capabilities" / "capability-registry.json"),
    "max_bytes": 4096,
    "offset": 0,
    "as_text": True,
  },
  "intent": {
    "goal": "Coverage stamp policy-eval regression",
    "constraints": {},
    "requested_action": "FS_READ",
    "inputs": [],
    "expected_outputs": [
      {"ref": "file:path", "value": str(root / "capabilities" / "capability-registry.json")}
    ],
  },
}
if include_stamp:
  intent["coverage_stamp"] = json.loads((fix / fixture_name).read_text(encoding="utf-8"))
out.write_text(json.dumps(intent, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

normalize_record() {
  local src="$1"
  local out="$2"
  python3 - <<'PY' "$src" "$out"
import json,sys,pathlib
src = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
doc = json.loads(src.read_text(encoding='utf-8'))
for key in ["timestamp_utc", "session_id", "request_id", "record_hash", "signature", "process_id"]:
    doc.pop(key, None)
if isinstance(doc.get("normalized_args"), dict):
    for k in ["canonical_path", "canonical_src_path", "canonical_dst_path"]:
        doc["normalized_args"].pop(k, None)
if isinstance(doc.get("policy_inputs"), dict):
    doc["policy_inputs"].pop("canonical_path", None)
if isinstance(doc.get("tool_args_redacted"), dict):
    doc["tool_args_redacted"].pop("canonical_path", None)
if isinstance(doc.get("intent"), dict):
    for item in doc["intent"].get("expected_outputs", []):
        if isinstance(item, dict) and item.get("ref") == "file:path":
            item["value"] = "<path-redacted>"
out.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding='utf-8')
PY
}

extract_summary() {
  python3 - <<'PY' "$1"
import json,sys
doc = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
s = doc.get('coverage_stamp_summary', {})
print(f"{s.get('overall_status','')}|{s.get('reason_code','')}|{doc.get('policy_decision','')}")
PY
}

run_case() {
  local name="$1"
  local fixture="$2"
  local include_stamp="$3"
  local required="$4"
  local exp_status="$5"
  local exp_reason="$6"
  local exp_decision="$7"

  build_intent "$fixture" "$include_stamp" "$TMPDIR_LOCAL/$name.intent.json"

  GOV_COVERAGE_STAMP_REQUIRED="$required" python3 "$EVAL" "$TMPDIR_LOCAL/$name.intent.json" > "$TMPDIR_LOCAL/$name.run1.raw"
  GOV_COVERAGE_STAMP_REQUIRED="$required" python3 "$EVAL" "$TMPDIR_LOCAL/$name.intent.json" > "$TMPDIR_LOCAL/$name.run2.raw"
  normalize_record "$TMPDIR_LOCAL/$name.run1.raw" "$TMPDIR_LOCAL/$name.run1.norm"
  normalize_record "$TMPDIR_LOCAL/$name.run2.raw" "$TMPDIR_LOCAL/$name.run2.norm"

  local sha1 sha2
  sha1="$(sha256_file "$TMPDIR_LOCAL/$name.run1.norm")"
  sha2="$(sha256_file "$TMPDIR_LOCAL/$name.run2.norm")"
  [[ "$sha1" == "$sha2" ]] || { echo "FAIL: $name nondeterministic output"; exit 1; }

  local summary status reason decision
  summary="$(extract_summary "$TMPDIR_LOCAL/$name.run1.norm")"
  IFS='|' read -r status reason decision <<EOF
$summary
EOF

  [[ "$status" == "$exp_status" ]] || { echo "FAIL: $name overall_status expected=$exp_status actual=$status"; exit 1; }
  [[ "$reason" == "$exp_reason" ]] || { echo "FAIL: $name reason_code expected=$exp_reason actual=$reason"; exit 1; }
  [[ "$decision" == "$exp_decision" ]] || { echo "FAIL: $name decision expected=$exp_decision actual=$decision"; exit 1; }

  echo "CASE_PASS name=$name required=$required overall_status=$status reason_code=$reason policy_decision=$decision sha256_run1=$sha1 sha256_run2=$sha2"
}

echo "--- T-COVERAGE-POLICY-MATRIX: expanded policy-eval coverage matrix ---"
run_case complete_v1 complete_v1.json 1 1 complete COVERAGE_STAMP_OK DENY
run_case minimal_valid_required_only minimal_valid_required_only.json 1 1 complete COVERAGE_STAMP_OK DENY
run_case multiple_surfaces_valid multiple_surfaces_valid.json 1 1 complete COVERAGE_STAMP_OK DENY
run_case missing_required missing_required.json 0 1 missing COVERAGE_STAMP_MISSING DENY
run_case optional_absent optional_absent.json 0 0 missing COVERAGE_STAMP_MISSING DENY
run_case partial_required partial_required.json 1 1 partial COVERAGE_STAMP_PARTIAL DENY
run_case mixed_required_optional_partial mixed_required_optional_partial.json 1 1 partial COVERAGE_STAMP_PARTIAL DENY
run_case order_invalid order_invalid.json 1 1 missing COVERAGE_STAMP_ORDER_INVALID DENY
run_case non_canonical_surface_order non_canonical_surface_order.json 1 1 missing COVERAGE_STAMP_ORDER_INVALID DENY
run_case deep_order_invalid deep_order_invalid.json 1 1 missing COVERAGE_STAMP_ORDER_INVALID DENY
run_case generated_from_unsorted generated_from_unsorted.json 1 1 missing COVERAGE_STAMP_ORDER_INVALID DENY
run_case evidence_sources_unsorted evidence_sources_unsorted.json 1 1 missing COVERAGE_STAMP_ORDER_INVALID DENY
run_case unknown_version unknown_version.json 1 1 missing COVERAGE_STAMP_VERSION_UNSUPPORTED DENY
run_case unknown_top_level_key unknown_top_level_key.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case wrong_type_fields wrong_type_fields.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case generated_from_not_array generated_from_not_array.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case generated_from_duplicate generated_from_duplicate.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case overall_status_mismatch overall_status_mismatch.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case overall_status_wrong_type overall_status_wrong_type.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case missing_surfaces_field missing_surfaces_field.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case empty_surfaces empty_surfaces.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case invalid_reason_code invalid_reason_code.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case missing_required_field_per_surface missing_required_field_per_surface.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case extra_unknown_field_inside_surface extra_unknown_field_inside_surface.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case non_canonical_capability_order non_canonical_capability_order.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case surfaces_not_array surfaces_not_array.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case surfaces_item_wrong_type surfaces_item_wrong_type.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case surface_id_not_string surface_id_not_string.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case required_field_null required_field_null.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case required_field_empty_string required_field_empty_string.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case duplicate_surface duplicate_surface.json 1 1 missing COVERAGE_STAMP_MALFORMED DENY
run_case invalid_enum_value invalid_enum_value.json 1 1 missing COVERAGE_STAMP_SURFACE_UNKNOWN DENY

echo "Summary: policy-eval coverage matrix complete"
