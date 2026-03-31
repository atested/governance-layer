#!/usr/bin/env bash
# test_replay.sh — Replay verifier tests for governance decision records.
#
# T-REPLAY-001: Replay a known DENY record (FS_WRITE overwrite-mismatch).
#   Expect: replay-record.py exit 0 and PASS output.
#
# T-REPLAY-002: Replay a known ALLOW record (FS_READ within caps).
#   Expect: exit 0 and PASS output.
#
# T-REPLAY-003 (tamper): Flip one char in request_bytes_b64 of a record.
#   Expect: exit 2 with "request_hash mismatch" message (fail-closed).
#
# T-REPLAY-004 (registry drift): Controlled registry byte swap with restore.
#   Re-serialize the current registry JSON into a different byte layout
#   (same semantics, different hash), swap it in for replay, then restore.
#   Expect: replay-record.py detects cap_registry_hash mismatch and exits 1.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
REPLAY="$ROOT/scripts/replay-record.py"
VERIFY="$ROOT/scripts/verify-record.py"
FIXTURES="$ROOT/tests/fixtures"
REGISTRY="$ROOT/capabilities/capability-registry.json"

pass=0
fail=0

check_exit () {
  local name="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS: $name (exit=$got)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (exit got=$got, want=$want)"
    fail=$((fail+1))
  fi
}

assert_contains () {
  local name="$1" text="$2" expect="$3"
  if echo "$text" | grep -q "$expect"; then
    echo "PASS: $name (contains '$expect')"
    pass=$((pass+1))
  else
    echo "FAIL: $name (missing '$expect')"
    echo "$text"
    fail=$((fail+1))
  fi
}

sha256_file () {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

verify_hash () {
  local name="$1" json_file="$2"
  if "$VERIFY" "$json_file" >/dev/null 2>&1; then
    echo "PASS: $name (record_hash verified)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (record_hash verify failed)"
    "$VERIFY" "$json_file" || true
    fail=$((fail+1))
  fi
}

mkdir -p "$ROOT/LOGS"

# ---------------------------------------------------------------------------
# T-REPLAY-001: Replay a DENY record
# Source: canon_001a.json (FS_WRITE overwrite mismatch → DENY RC-FS-OVERWRITE-DISALLOWED)
# ---------------------------------------------------------------------------
echo "--- T-REPLAY-001: replay DENY record ---"

python3 "$EVAL" "$FIXTURES/canon_001a.json" > "$ROOT/LOGS/t-replay-001.record.json"
verify_hash "T-REPLAY-001 baseline verify-record" "$ROOT/LOGS/t-replay-001.record.json"

out_001="$(python3 "$REPLAY" "$ROOT/LOGS/t-replay-001.record.json" 2>&1)"
rc_001=$?
check_exit  "T-REPLAY-001 exit 0"     "$rc_001"  "0"
assert_contains "T-REPLAY-001 PASS output" "$out_001" "PASS: replay matches original"
assert_contains "T-REPLAY-001 shows DENY"  "$out_001" "decision=DENY"
assert_contains "T-REPLAY-001 shows RC"    "$out_001" "RC-FS-OVERWRITE-DISALLOWED"

echo

# ---------------------------------------------------------------------------
# T-REPLAY-002: Replay a portable FS_READ record
# Decision can vary by allowed-root policy configuration across environments;
# replay correctness is that it reproduces the original deterministic output.
# ---------------------------------------------------------------------------
echo "--- T-REPLAY-002: replay ALLOW record ---"

python3 - <<'PY' "$ROOT/LOGS/t-replay-002.intent.json" "$ROOT/capabilities/capability-registry.json"
import json, sys
intent_path, cap_path = sys.argv[1], sys.argv[2]
doc = {
    "tool": "FS_READ",
    "args": {
        "path": cap_path,
        "max_bytes": 4096,
        "offset": 0,
        "as_text": True,
    },
    "intent": {
        "goal": "Read capability registry (max_bytes within hard limit).",
        "constraints": {},
        "requested_action": "FS_READ",
        "inputs": [],
        "expected_outputs": [{"ref": "file:path", "value": cap_path}],
    },
}
with open(intent_path, "w", encoding="utf-8") as f:
    json.dump(doc, f, indent=2)
PY

python3 "$EVAL" "$ROOT/LOGS/t-replay-002.intent.json" > "$ROOT/LOGS/t-replay-002.record.json"
verify_hash "T-REPLAY-002 baseline verify-record" "$ROOT/LOGS/t-replay-002.record.json"

out_002="$(python3 "$REPLAY" "$ROOT/LOGS/t-replay-002.record.json" 2>&1)"
rc_002=$?
check_exit  "T-REPLAY-002 exit 0"      "$rc_002"  "0"
assert_contains "T-REPLAY-002 PASS output" "$out_002" "PASS: replay matches original"
assert_contains "T-REPLAY-002 shows FS_READ tool" "$out_002" "tool=FS_READ"

echo

# ---------------------------------------------------------------------------
# T-REPLAY-003: Tamper test — flip one char in request_bytes_b64
# Expected: exit 2 with "request_hash mismatch" (fail-closed before evaluation).
# ---------------------------------------------------------------------------
echo "--- T-REPLAY-003: tamper request_bytes_b64 → fail-closed ---"

# Produce a fresh DENY record to tamper with.
python3 "$EVAL" "$FIXTURES/canon_001a.json" > "$ROOT/LOGS/t-replay-003-original.record.json"

# Flip the last character of request_bytes_b64 (stay in valid base64 charset).
python3 - <<'PY' "$ROOT/LOGS/t-replay-003-original.record.json" "$ROOT/LOGS/t-replay-003-tampered.record.json"
import base64, json, sys

src, dst = sys.argv[1], sys.argv[2]
with open(src) as f:
    rec = json.load(f)

# Decode bytes, flip one byte in the middle, re-encode → valid base64, wrong hash.
raw = bytearray(base64.b64decode(rec["request_bytes_b64"]))
mid = len(raw) // 2
raw[mid] = (raw[mid] ^ 0xFF) & 0xFF
rec["request_bytes_b64"] = base64.b64encode(bytes(raw)).decode("ascii")
# request_hash intentionally left as-is → mismatch on decode-then-hash.

with open(dst, "w") as f:
    json.dump(rec, f, indent=2)
PY

rc_003=0
out_003="$(python3 "$REPLAY" "$ROOT/LOGS/t-replay-003-tampered.record.json" 2>&1)" || rc_003=$?
check_exit      "T-REPLAY-003 exit 2 (fail-closed)"     "$rc_003" "2"
assert_contains "T-REPLAY-003 hash mismatch message"    "$out_003" "request_hash mismatch"

echo

# ---------------------------------------------------------------------------
# T-REPLAY-004: Registry drift detection via controlled byte-level registry swap
# Re-serialize the real registry to alternate JSON formatting (same data), swap
# it in only for the replay call, and assert fail-closed mismatch on cap hash.
# ---------------------------------------------------------------------------
echo "--- T-REPLAY-004: registry drift via controlled registry swap ---"

# Produce a fresh record bound to the current on-disk registry.
python3 "$EVAL" "$FIXTURES/canon_002a.json" > "$ROOT/LOGS/t-replay-004.record.json"
verify_hash "T-REPLAY-004 baseline verify-record" "$ROOT/LOGS/t-replay-004.record.json"

alt_registry="$ROOT/LOGS/t-replay-004.alt-registry.json"
backup_registry="$ROOT/LOGS/t-replay-004.registry.backup.json"

# Deterministically re-encode the current registry to preserve semantics while
# changing raw bytes (and therefore the bound cap_registry_hash).
python3 - <<'PY' "$REGISTRY" "$alt_registry"
import json, sys

src, dst = sys.argv[1], sys.argv[2]
with open(src, "r", encoding="utf-8") as f:
    reg = json.load(f)
with open(dst, "w", encoding="utf-8") as f:
    json.dump(reg, f, sort_keys=True, separators=(",", ":"))
    f.write("\n")
PY

cp "$REGISTRY" "$backup_registry"
restore_registry () {
  if [[ -f "$backup_registry" ]]; then
    cp "$backup_registry" "$REGISTRY"
    rm -f "$backup_registry"
  fi
}
trap restore_registry EXIT

cp "$alt_registry" "$REGISTRY"
rc_004=0
out_004="$(python3 "$REPLAY" "$ROOT/LOGS/t-replay-004.record.json" 2>&1)" || rc_004=$?
restore_registry
trap - EXIT

check_exit      "T-REPLAY-004 exit 1 (registry drift fail-closed)" "$rc_004" "1"
assert_contains "T-REPLAY-004 mismatch summary" "$out_004" "FAIL: replay mismatch on 1 invariant(s):"
assert_contains "T-REPLAY-004 cap hash field"   "$out_004" "field:    cap_registry_hash"
assert_contains "T-REPLAY-004 sha256 markers"   "$out_004" "sha256:"
assert_contains "T-REPLAY-004 mismatch kind"    "$out_004" "kind:     value"

echo
# ---------------------------------------------------------------------------
# T-REPLAY-005..009: Broaden deterministic mismatch matrix using replay-test
# mutation hooks in replay-record.py (task-scoped negative controls).
# All cases must exit 1 and produce deterministic audit report JSON.
# ---------------------------------------------------------------------------
echo "--- T-REPLAY-005..009: invariant mismatch matrix via controlled replay mutations ---"

python3 "$EVAL" "$FIXTURES/canon_002a.json" > "$ROOT/LOGS/t-replay-005-base.record.json"
verify_hash "T-REPLAY-005 base record verify-record" "$ROOT/LOGS/t-replay-005-base.record.json"

run_mutation_case () {
  local case_id="$1" mode="$2" expect_field="$3" expect_kind="$4"
  local report1="$ROOT/LOGS/${case_id}.report1.json"
  local report2="$ROOT/LOGS/${case_id}.report2.json"
  local out1 out2 rc1 rc2 sha1 sha2

  rc1=0
  out1="$(GOV_REPLAY_TEST_MUTATION="$mode" python3 "$REPLAY" --audit-report-json "$report1" "$ROOT/LOGS/t-replay-005-base.record.json" 2>&1)" || rc1=$?
  check_exit "${case_id} exit 1" "$rc1" "1"
  assert_contains "${case_id} mismatch field" "$out1" "field:    $expect_field"
  assert_contains "${case_id} mismatch kind" "$out1" "kind:     $expect_kind"

  rc2=0
  out2="$(GOV_REPLAY_TEST_MUTATION="$mode" python3 "$REPLAY" --audit-report-json "$report2" "$ROOT/LOGS/t-replay-005-base.record.json" 2>&1)" || rc2=$?
  check_exit "${case_id} repeat exit 1" "$rc2" "1"
  assert_contains "${case_id} repeat mismatch field" "$out2" "field:    $expect_field"
  assert_contains "${case_id} repeat mismatch kind" "$out2" "kind:     $expect_kind"

  sha1="$(sha256_file "$report1")"
  sha2="$(sha256_file "$report2")"
  if [[ "$sha1" == "$sha2" ]]; then
    echo "PASS: ${case_id} report sha256 stable ($sha1)"
    pass=$((pass+1))
  else
    echo "FAIL: ${case_id} report sha256 drift ($sha1 != $sha2)"
    fail=$((fail+1))
  fi

  python3 - <<'PY' "$report1" "$expect_field" "$expect_kind" "$case_id"
import json, sys
path, expect_field, expect_kind, case_id = sys.argv[1:5]
doc = json.load(open(path, encoding="utf-8"))
assert doc["report_version"] == "replay_audit_summary_v1"
assert doc["record_counts"]["mismatched"] == 1
assert doc["record_counts"]["fatal"] == 0
assert len(doc["records"]) == 1
m = doc["records"][0]["mismatches"]
fields = [x["field"] for x in m]
kinds = [x.get("kind") for x in m]
assert expect_field in fields, (case_id, fields)
assert expect_kind in kinds, (case_id, kinds)
print(f"PASS: {case_id} audit report includes field={expect_field} kind={expect_kind}")
print("MISMATCH_FIELDS=" + ",".join(sorted(fields)))
PY
}

run_mutation_case "T-REPLAY-005 (missing invariant field)" "drop_normalized_args" "normalized_args" "missing"
run_mutation_case "T-REPLAY-006 (extra invariant field)" "add_extra_invariant" "__replay_test_extra_invariant__" "extra"
run_mutation_case "T-REPLAY-007 (value mismatch on stable field)" "mismatch_tool_value" "tool" "value"
run_mutation_case "T-REPLAY-008 (type mismatch on stable field)" "type_mismatch_cap_registry_hash" "cap_registry_hash" "type"

run_mutation_case "T-REPLAY-009 (reason_codes mismatch)" "mismatch_reason_codes_order" "reason_codes" "value"

echo
# ---------------------------------------------------------------------------
# T-REPLAY-010..015: strictness controls for missing/extra invariant fields
# Validate error|mismatch|ignore behavior and audit report determinism.
# ---------------------------------------------------------------------------
echo "--- T-REPLAY-010..015: strictness controls (missing/extra) ---"

strictness_case () {
  local case_id="$1" mutation="$2" s_missing="$3" s_extra="$4" want_rc="$5" expect_marker="$6" py_check="$7"
  local report1="$ROOT/LOGS/${case_id}.strict1.json"
  local report2="$ROOT/LOGS/${case_id}.strict2.json"
  local out1 out2 rc1 rc2 sha1 sha2

  rc1=0
  out1="$(GOV_REPLAY_TEST_MUTATION="$mutation" python3 "$REPLAY" --strict-missing "$s_missing" --strict-extra "$s_extra" --audit-report-json "$report1" "$ROOT/LOGS/t-replay-005-base.record.json" 2>&1)" || rc1=$?
  check_exit "${case_id} rc" "$rc1" "$want_rc"
  assert_contains "${case_id} marker" "$out1" "$expect_marker"

  rc2=0
  out2="$(GOV_REPLAY_TEST_MUTATION="$mutation" python3 "$REPLAY" --strict-missing "$s_missing" --strict-extra "$s_extra" --audit-report-json "$report2" "$ROOT/LOGS/t-replay-005-base.record.json" 2>&1)" || rc2=$?
  check_exit "${case_id} repeat rc" "$rc2" "$want_rc"
  assert_contains "${case_id} repeat marker" "$out2" "$expect_marker"

  sha1="$(sha256_file "$report1")"
  sha2="$(sha256_file "$report2")"
  if [[ "$sha1" == "$sha2" ]]; then
    echo "PASS: ${case_id} strictness report sha256 stable ($sha1)"
    pass=$((pass+1))
  else
    echo "FAIL: ${case_id} strictness report sha256 drift ($sha1 != $sha2)"
    fail=$((fail+1))
  fi

  python3 - <<'PY' "$report1" "$py_check" "$case_id"
import json, sys
path, mode_check, case_id = sys.argv[1:4]
doc = json.load(open(path, encoding="utf-8"))
assert doc["report_version"] == "replay_audit_summary_v1"
assert "strictness" in doc and "missing" in doc["strictness"] and "extra" in doc["strictness"]
rec = doc["records"][0]
checks = set(mode_check.split(","))
if "expect_fatal" in checks:
    assert rec["kind"] == "fatal", (case_id, rec["kind"])
    assert rec.get("fatal_reason"), case_id
if "expect_mismatch_missing" in checks:
    fields = [m["field"] for m in rec.get("mismatches", [])]
    kinds = [m.get("kind") for m in rec.get("mismatches", [])]
    assert "normalized_args" in fields and "missing" in kinds, (case_id, fields, kinds)
if "expect_mismatch_extra" in checks:
    fields = [m["field"] for m in rec.get("mismatches", [])]
    kinds = [m.get("kind") for m in rec.get("mismatches", [])]
    assert "__replay_test_extra_invariant__" in fields and "extra" in kinds, (case_id, fields, kinds)
if "expect_ignored_missing" in checks:
    fields = [m["field"] for m in rec.get("ignored_findings", [])]
    kinds = [m.get("kind") for m in rec.get("ignored_findings", [])]
    assert "normalized_args" in fields and "missing" in kinds, (case_id, fields, kinds)
if "expect_ignored_extra" in checks:
    fields = [m["field"] for m in rec.get("ignored_findings", [])]
    kinds = [m.get("kind") for m in rec.get("ignored_findings", [])]
    assert "__replay_test_extra_invariant__" in fields and "extra" in kinds, (case_id, fields, kinds)
print(f"PASS: {case_id} report fields match strictness semantics")
print("STRICTNESS=" + doc["strictness"]["missing"] + "/" + doc["strictness"]["extra"])
print("INVARIANT_COUNTS=" + json.dumps(doc["invariant_counts"], sort_keys=True, separators=(',',':')))
print("FATAL_REASON=" + str(rec.get("fatal_reason")))
print("IGNORED_FINDINGS_COUNT=" + str(len(rec.get("ignored_findings", []))))
PY
}

# Missing invariant field strictness modes
strictness_case "T-REPLAY-010 (missing strict=mismatch)" "drop_normalized_args" "mismatch" "mismatch" "1" "kind:     missing" "expect_mismatch_missing"
strictness_case "T-REPLAY-011 (missing strict=ignore)" "drop_normalized_args" "ignore" "mismatch" "0" "ignored_field: normalized_args" "expect_ignored_missing"
strictness_case "T-REPLAY-012 (missing strict=error)" "drop_normalized_args" "error" "mismatch" "2" "strict_missing=error triggered for field normalized_args" "expect_fatal"

# Extra invariant field strictness modes
strictness_case "T-REPLAY-013 (extra strict=mismatch)" "add_extra_invariant" "mismatch" "mismatch" "1" "kind:     extra" "expect_mismatch_extra"
strictness_case "T-REPLAY-014 (extra strict=ignore)" "add_extra_invariant" "mismatch" "ignore" "0" "ignored_field: __replay_test_extra_invariant__" "expect_ignored_extra"
strictness_case "T-REPLAY-015 (extra strict=error)" "add_extra_invariant" "mismatch" "error" "2" "strict_extra=error triggered for field __replay_test_extra_invariant__" "expect_fatal"

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
