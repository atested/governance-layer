#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
REPLAY="$ROOT/scripts/replay-record.py"
VERIFY="$ROOT/scripts/verify-record.py"
FIXTURES="$ROOT/tests/fixtures"
REGISTRY="$ROOT/capabilities/capability-registry.json"

TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task115-audit.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

assert_eq() {
  local name="$1" a="$2" b="$3"
  [[ "$a" == "$b" ]] || { echo "FAIL: $name ($a != $b)"; exit 1; }
  echo "PASS: $name"
}

assert_ne() {
  local name="$1" a="$2" b="$3"
  [[ "$a" != "$b" ]] || { echo "FAIL: $name ($a == $b)"; exit 1; }
  echo "PASS: $name"
}

assert_contains() {
  local name="$1" text="$2" needle="$3"
  [[ "$text" == *"$needle"* ]] || { echo "FAIL: $name (missing '$needle')"; exit 1; }
  echo "PASS: $name"
}

echo "--- T-REPLAY-AUDIT-001: no-mismatch report deterministic across two runs ---"
REC_OK="$TMPDIR_LOCAL/ok.record.json"
python3 "$EVAL" "$FIXTURES/canon_002a.json" > "$REC_OK"
"$VERIFY" "$REC_OK" >/dev/null

RPT_OK1="$TMPDIR_LOCAL/ok1.report.json"
RPT_OK2="$TMPDIR_LOCAL/ok2.report.json"
python3 "$REPLAY" --audit-report-json "$RPT_OK1" "$REC_OK" >/dev/null
python3 "$REPLAY" --audit-report-json "$RPT_OK2" "$REC_OK" >/dev/null
RPT_OK1_SHA="$(sha256_file "$RPT_OK1")"
RPT_OK2_SHA="$(sha256_file "$RPT_OK2")"
assert_eq "no-mismatch report sha256 stable" "$RPT_OK1_SHA" "$RPT_OK2_SHA"
echo "REPORT_SHA256_OK_STABLE=yes"

python3 - <<'PY' "$RPT_OK1"
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
assert doc["report_version"] == "replay_audit_summary_v1"
assert doc["record_counts"] == {"fatal": 0, "matched": 1, "mismatched": 0, "total": 1}
assert doc["invariant_counts"]["mismatched"] == 0
assert doc["invariant_counts"]["matched"] == 6
assert doc["invariant_counts"]["total_checked"] == 6
assert doc["records"][0]["kind"] == "pass"
assert doc["records"][0]["mismatches"] == []
print("PASS: no-mismatch report shape deterministic and clean")
print("REPORT_KEYS=" + ",".join(sorted(doc.keys())))
PY

echo
echo "--- T-REPLAY-AUDIT-002: mismatch report deterministic across two runs (registry drift) ---"
REC_BAD="$TMPDIR_LOCAL/mismatch.record.json"
python3 "$EVAL" "$FIXTURES/canon_002a.json" > "$REC_BAD"
"$VERIFY" "$REC_BAD" >/dev/null

ALT_REG="$TMPDIR_LOCAL/alt-registry.json"
BAK_REG="$TMPDIR_LOCAL/registry.backup.json"
python3 - <<'PY' "$REGISTRY" "$ALT_REG"
import json, sys
src, dst = sys.argv[1:3]
with open(src, "r", encoding="utf-8") as f:
    reg = json.load(f)
with open(dst, "w", encoding="utf-8") as f:
    json.dump(reg, f, sort_keys=True, separators=(",", ":"))
    f.write("\n")
PY

restore_registry() {
  if [[ -f "$BAK_REG" ]]; then
    cp "$BAK_REG" "$REGISTRY"
    rm -f "$BAK_REG"
  fi
}
trap 'restore_registry; rm -rf "$TMPDIR_LOCAL"' EXIT

RPT_BAD1="$TMPDIR_LOCAL/bad1.report.json"
RPT_BAD2="$TMPDIR_LOCAL/bad2.report.json"
cp "$REGISTRY" "$BAK_REG"
cp "$ALT_REG" "$REGISTRY"
set +e
OUT_BAD1="$(python3 "$REPLAY" --audit-report-json "$RPT_BAD1" "$REC_BAD" 2>&1)"
RC_BAD1=$?
OUT_BAD2="$(python3 "$REPLAY" --audit-report-json "$RPT_BAD2" "$REC_BAD" 2>&1)"
RC_BAD2=$?
set -e
restore_registry

assert_eq "mismatch run1 exit" "$RC_BAD1" "1"
assert_eq "mismatch run2 exit" "$RC_BAD2" "1"
assert_contains "mismatch stdout reports cap hash field (run1)" "$OUT_BAD1" "field:    cap_registry_hash"
assert_contains "mismatch stdout reports cap hash field (run2)" "$OUT_BAD2" "field:    cap_registry_hash"

RPT_BAD1_SHA="$(sha256_file "$RPT_BAD1")"
RPT_BAD2_SHA="$(sha256_file "$RPT_BAD2")"
assert_eq "mismatch report sha256 stable" "$RPT_BAD1_SHA" "$RPT_BAD2_SHA"
assert_ne "mismatch vs clean report hash differs" "$RPT_BAD1_SHA" "$RPT_OK1_SHA"
echo "REPORT_SHA256_MISMATCH_STABLE=yes"

python3 - <<'PY' "$RPT_BAD1"
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
assert doc["record_counts"]["mismatched"] == 1
assert doc["record_counts"]["matched"] == 0
assert doc["record_counts"]["fatal"] == 0
assert doc["invariant_counts"]["mismatched"] == 1
assert doc["invariant_counts"]["matched"] == 5
assert doc["invariant_counts"]["total_checked"] == 6
fields = [m["field"] for m in doc["records"][0]["mismatches"]]
assert fields == sorted(fields)
assert fields == ["cap_registry_hash"], fields
print("PASS: mismatch report shape deterministic and ordered")
print("MISMATCH_FIELDS=" + ",".join(fields))
PY

echo
echo "Summary: replay audit report determinism tests complete"
