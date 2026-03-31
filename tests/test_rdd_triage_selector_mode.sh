#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS_TRIAGE="$ROOT/scripts/rdd-pass-triage.sh"
VERIFY="$ROOT/scripts/verify-record.py"
FIXTURES="$ROOT/tests/fixtures"
LOG_DIR="$ROOT/LOGS"
RUNTIME_DIR="$ROOT/out/rdd"

pass=0
fail=0

pass_case () {
  local id="$1" msg="$2"
  echo "PASS: $id $msg"
  pass=$((pass+1))
}

fail_case () {
  local id="$1" msg="$2"
  echo "FAIL: $id $msg"
  fail=$((fail+1))
}

json_get () {
  local file="$1" path="$2"
  python3 - <<'PY' "$file" "$path"
import json, sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
cur = obj
for part in sys.argv[2].split('.'):
    if part.isdigit():
        cur = cur[int(part)]
    else:
        cur = cur.get(part)
print(json.dumps(cur) if isinstance(cur, (dict, list)) else str(cur))
PY
}

mk_signing_pair () {
  local key_path="$1" pub_path="$2"
  cat > "$key_path" <<'PEM'
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIKY6z3CMVvjJkqQW3AX6mEGoVYLRsKcJsteU8h1Hn0pG
-----END PRIVATE KEY-----
PEM
  python3 <<PY
from pathlib import Path
from cryptography.hazmat.primitives import serialization
key = Path("$key_path")
priv = serialization.load_pem_private_key(key.read_bytes(), password=None)
pub = priv.public_key()
Path("$pub_path").write_bytes(pub.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
))
PY
}

mkdir -p "$LOG_DIR" "$RUNTIME_DIR"
export GOV_CANONICAL_REPO_PATH="$ROOT"
export GOV_RUNTIME_PATH="$ROOT/out/runtime"

SRC_PATH="$RUNTIME_DIR/phase14-selector-src.txt"
DST_EXISTS_PATH="$RUNTIME_DIR/phase14-selector-dst-exists.txt"
printf 'phase14-selector-src\n' > "$SRC_PATH"
printf 'phase14-selector-existing\n' > "$DST_EXISTS_PATH"

TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/rdd-triage-selector-mode.XXXXXX")"
cleanup() { rm -rf "$TMPDIR_LOCAL"; }
trap cleanup EXIT

KEY_PATH="$TMPDIR_LOCAL/key.pem"
PUB_PATH="$TMPDIR_LOCAL/key.pub.pem"
mk_signing_pair "$KEY_PATH" "$PUB_PATH"
export GOV_SIGNING_KEY_PATH="$KEY_PATH"
export GOV_VERIFY_KEY_PATH="$PUB_PATH"

# Positive: explicit selector mode wired from intent through wrapper.
OUT_EXPLICIT="$TMPDIR_LOCAL/explicit.record.json"
ERR_EXPLICIT="$TMPDIR_LOCAL/explicit.stderr.txt"
CHAIN_EXPLICIT="$TMPDIR_LOCAL/explicit.chain.jsonl"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$CHAIN_EXPLICIT" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_explicit.json" >"$OUT_EXPLICIT" 2>"$ERR_EXPLICIT"
rc_explicit="$?"
set -e

[[ "$rc_explicit" -eq 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-001" "explicit mode invocation succeeds" \
  || fail_case "T-RDD-TRIAGE-MODE-001" "explicit mode invocation failed ($rc_explicit)"

[[ "$(json_get "$OUT_EXPLICIT" "record_type")" == "triage_decision" ]] \
  && pass_case "T-RDD-TRIAGE-MODE-002" "triage record emitted in explicit mode" \
  || fail_case "T-RDD-TRIAGE-MODE-002" "expected triage_decision output"

grep -q "RDD_TRIAGE_SELECTOR_MODE_APPLIED mode=explicit" "$ERR_EXPLICIT" \
  && pass_case "T-RDD-TRIAGE-MODE-003" "explicit mode wiring marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-003" "explicit mode wiring marker missing"

python3 "$VERIFY" "$OUT_EXPLICIT" >/dev/null \
  && pass_case "T-RDD-TRIAGE-MODE-004" "verify-record passes on explicit mode output" \
  || fail_case "T-RDD-TRIAGE-MODE-004" "verify-record failed on explicit mode output"

# Positive: compat mode path remains valid for single-case legacy criteria fixture.
OUT_COMPAT="$TMPDIR_LOCAL/compat.record.json"
ERR_COMPAT="$TMPDIR_LOCAL/compat.stderr.txt"
CHAIN_COMPAT="$TMPDIR_LOCAL/compat.chain.jsonl"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_legacy_single_case.json" \
GOV_DECISION_CHAIN_PATH="$CHAIN_COMPAT" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_compat.json" >"$OUT_COMPAT" 2>"$ERR_COMPAT"
rc_compat="$?"
set -e

[[ "$rc_compat" -eq 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-005" "compat mode invocation succeeds" \
  || fail_case "T-RDD-TRIAGE-MODE-005" "compat mode invocation failed ($rc_compat)"

grep -q "RDD_TRIAGE_SELECTOR_MODE_APPLIED mode=compat_legacy_single_case" "$ERR_COMPAT" \
  && pass_case "T-RDD-TRIAGE-MODE-006" "compat mode wiring marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-006" "compat mode wiring marker missing"

# Positive: canonical request mixed-case explicit mode normalizes and succeeds.
OUT_CASE_EXPLICIT="$TMPDIR_LOCAL/case-explicit.record.json"
ERR_CASE_EXPLICIT="$TMPDIR_LOCAL/case-explicit.stderr.txt"
CHAIN_CASE_EXPLICIT="$TMPDIR_LOCAL/case-explicit.chain.jsonl"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$CHAIN_CASE_EXPLICIT" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase19_selector_mode_intent_canonical_case_explicit.json" >"$OUT_CASE_EXPLICIT" 2>"$ERR_CASE_EXPLICIT"
rc_case_explicit="$?"
set -e

[[ "$rc_case_explicit" -eq 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-006E" "canonical mixed-case explicit selector mode normalizes and succeeds" \
  || fail_case "T-RDD-TRIAGE-MODE-006E" "canonical mixed-case explicit selector mode failed ($rc_case_explicit)"

grep -q "RDD_TRIAGE_SELECTOR_MODE_APPLIED mode=explicit" "$ERR_CASE_EXPLICIT" \
  && pass_case "T-RDD-TRIAGE-MODE-006F" "canonical mixed-case explicit marker normalized to explicit" \
  || fail_case "T-RDD-TRIAGE-MODE-006F" "canonical mixed-case explicit normalized marker missing"

# Positive: canonical request mixed-case compat mode normalizes and succeeds.
OUT_CASE_COMPAT="$TMPDIR_LOCAL/case-compat.record.json"
ERR_CASE_COMPAT="$TMPDIR_LOCAL/case-compat.stderr.txt"
CHAIN_CASE_COMPAT="$TMPDIR_LOCAL/case-compat.chain.jsonl"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_legacy_single_case.json" \
GOV_DECISION_CHAIN_PATH="$CHAIN_CASE_COMPAT" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase19_selector_mode_intent_canonical_case_compat.json" >"$OUT_CASE_COMPAT" 2>"$ERR_CASE_COMPAT"
rc_case_compat="$?"
set -e

[[ "$rc_case_compat" -eq 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-006G" "canonical mixed-case compat selector mode normalizes and succeeds" \
  || fail_case "T-RDD-TRIAGE-MODE-006G" "canonical mixed-case compat selector mode failed ($rc_case_compat)"

grep -q "RDD_TRIAGE_SELECTOR_MODE_APPLIED mode=compat_legacy_single_case" "$ERR_CASE_COMPAT" \
  && pass_case "T-RDD-TRIAGE-MODE-006H" "canonical mixed-case compat marker normalized to compat_legacy_single_case" \
  || fail_case "T-RDD-TRIAGE-MODE-006H" "canonical mixed-case compat normalized marker missing"

# Positive: absent selector mode remains backward-compatible via default mode.
OUT_ABSENT="$TMPDIR_LOCAL/absent.record.json"
ERR_ABSENT="$TMPDIR_LOCAL/absent.stderr.txt"
CHAIN_ABSENT="$TMPDIR_LOCAL/absent.chain.jsonl"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_legacy_single_case.json" \
GOV_DECISION_CHAIN_PATH="$CHAIN_ABSENT" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_absent.json" >"$OUT_ABSENT" 2>"$ERR_ABSENT"
rc_absent="$?"
set -e

[[ "$rc_absent" -eq 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-006A" "absent selector mode uses default compatibility path" \
  || fail_case "T-RDD-TRIAGE-MODE-006A" "absent selector mode unexpectedly failed ($rc_absent)"

grep -q "RDD_TRIAGE_SELECTOR_MODE_APPLIED mode=compat_legacy_single_case source=default" "$ERR_ABSENT" \
  && pass_case "T-RDD-TRIAGE-MODE-006B" "default selector mode marker present when request omits selector mode" \
  || fail_case "T-RDD-TRIAGE-MODE-006B" "default selector mode marker missing for absent request mode"

# Positive: ambient mode cannot silently override request-bound mode.
OUT_AMBIENT="$TMPDIR_LOCAL/ambient.record.json"
ERR_AMBIENT="$TMPDIR_LOCAL/ambient.stderr.txt"
set +e
GOV_TRIAGE_SELECTOR_MODE="compat_legacy_single_case" \
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/ambient.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_explicit.json" >"$OUT_AMBIENT" 2>"$ERR_AMBIENT"
rc_ambient="$?"
set -e

[[ "$rc_ambient" -eq 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-006C" "request-bound explicit mode resists ambient override" \
  || fail_case "T-RDD-TRIAGE-MODE-006C" "ambient override protection path failed ($rc_ambient)"

grep -q "RDD_TRIAGE_SELECTOR_MODE_AMBIENT_IGNORED ambient=compat_legacy_single_case applied=explicit" "$ERR_AMBIENT" \
  && pass_case "T-RDD-TRIAGE-MODE-006D" "ambient override suppression marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-006D" "ambient override suppression marker missing"

# Negative: explicit mode + missing selector_map must fail closed.
ERR_MISSING_MAP="$TMPDIR_LOCAL/missing-map.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_missing_map.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/missing-map.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_explicit.json" >/dev/null 2>"$ERR_MISSING_MAP"
rc_missing_map="$?"
set -e

[[ "$rc_missing_map" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-007" "explicit missing selector_map fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-007" "explicit missing selector_map unexpectedly succeeded"

grep -q "TRIAGE_CRITERIA_SELECTOR_MAP_REQUIRED mode=explicit" "$ERR_MISSING_MAP" \
  && pass_case "T-RDD-TRIAGE-MODE-008" "explicit missing selector_map marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-008" "explicit missing selector_map marker absent"

# Negative: explicit mode + invalid selector_map schema must fail closed.
ERR_INVALID_MAP="$TMPDIR_LOCAL/invalid-map.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_invalid_map_type.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/invalid-map.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_explicit.json" >/dev/null 2>"$ERR_INVALID_MAP"
rc_invalid_map="$?"
set -e

[[ "$rc_invalid_map" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-009" "explicit invalid selector_map type fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-009" "explicit invalid selector_map type unexpectedly succeeded"

grep -q "TRIAGE_CRITERIA_SELECTOR_MAP_INVALID expected=object" "$ERR_INVALID_MAP" \
  && pass_case "T-RDD-TRIAGE-MODE-010" "explicit invalid selector_map marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010" "explicit invalid selector_map marker absent"

# Negative: invalid request-bound selector mode must fail closed.
ERR_INVALID_REQUEST_MODE="$TMPDIR_LOCAL/invalid-request-mode.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/invalid-request-mode.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase19_selector_mode_intent_canonical_case_invalid.json" >/dev/null 2>"$ERR_INVALID_REQUEST_MODE"
rc_invalid_request_mode="$?"
set -e

[[ "$rc_invalid_request_mode" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010A" "invalid request-bound selector mode fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010A" "invalid request-bound selector mode unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_INVALID mode=experimental_mode" "$ERR_INVALID_REQUEST_MODE" \
  && pass_case "T-RDD-TRIAGE-MODE-010B" "invalid request mode marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010B" "invalid request mode marker absent"

# Negative: canonical non-string selector mode must fail closed.
ERR_INVALID_REQUEST_MODE_NON_STRING="$TMPDIR_LOCAL/invalid-request-mode-non-string.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/invalid-request-mode-non-string.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase20_selector_mode_intent_canonical_non_string.json" >/dev/null 2>"$ERR_INVALID_REQUEST_MODE_NON_STRING"
rc_invalid_request_mode_non_string="$?"
set -e

[[ "$rc_invalid_request_mode_non_string" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010BA" "canonical non-string selector mode fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010BA" "canonical non-string selector mode unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_INVALID mode=<non_string_or_empty>" "$ERR_INVALID_REQUEST_MODE_NON_STRING" \
  && pass_case "T-RDD-TRIAGE-MODE-010BB" "canonical non-string invalid marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010BB" "canonical non-string invalid marker absent"

# Negative: canonical empty-string selector mode must fail closed.
ERR_INVALID_REQUEST_MODE_EMPTY="$TMPDIR_LOCAL/invalid-request-mode-empty.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/invalid-request-mode-empty.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase20_selector_mode_intent_canonical_empty_string.json" >/dev/null 2>"$ERR_INVALID_REQUEST_MODE_EMPTY"
rc_invalid_request_mode_empty="$?"
set -e

[[ "$rc_invalid_request_mode_empty" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010BC" "canonical empty-string selector mode fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010BC" "canonical empty-string selector mode unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_INVALID mode=<non_string_or_empty>" "$ERR_INVALID_REQUEST_MODE_EMPTY" \
  && pass_case "T-RDD-TRIAGE-MODE-010BD" "canonical empty-string invalid marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010BD" "canonical empty-string invalid marker absent"

# Negative: canonical invalid selector mode plus legacy aliases must fail closed as canonical invalid (not source conflict).
ERR_INVALID_CANONICAL_WITH_LEGACY_BOTH="$TMPDIR_LOCAL/invalid-canonical-with-legacy-both.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/invalid-canonical-with-legacy-both.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase20_selector_mode_intent_canonical_invalid_with_legacy_both_aliases.json" >/dev/null 2>"$ERR_INVALID_CANONICAL_WITH_LEGACY_BOTH"
rc_invalid_canonical_with_legacy_both="$?"
set -e

[[ "$rc_invalid_canonical_with_legacy_both" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010BE" "canonical invalid with legacy aliases fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010BE" "canonical invalid with legacy aliases unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_INVALID mode=experimental_mode" "$ERR_INVALID_CANONICAL_WITH_LEGACY_BOTH" \
  && pass_case "T-RDD-TRIAGE-MODE-010BF" "canonical invalid marker retained with legacy aliases" \
  || fail_case "T-RDD-TRIAGE-MODE-010BF" "canonical invalid marker missing with legacy aliases"

if grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_CONFLICT" "$ERR_INVALID_CANONICAL_WITH_LEGACY_BOTH"; then
  fail_case "T-RDD-TRIAGE-MODE-010BG" "canonical invalid with legacy aliases misclassified as source conflict"
else
  pass_case "T-RDD-TRIAGE-MODE-010BG" "canonical invalid with legacy aliases not misclassified as source conflict"
fi

# Negative: legacy alias source under intent.rdd must fail closed.
ERR_LEGACY_RDD="$TMPDIR_LOCAL/legacy-rdd.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-rdd.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_legacy_rdd_alias.json" >/dev/null 2>"$ERR_LEGACY_RDD"
rc_legacy_rdd="$?"
set -e

[[ "$rc_legacy_rdd" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010C" "legacy rdd selector_mode alias fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010C" "legacy rdd selector_mode alias unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_FORBIDDEN source=intent.rdd.selector_mode" "$ERR_LEGACY_RDD" \
  && pass_case "T-RDD-TRIAGE-MODE-010D" "legacy rdd alias marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010D" "legacy rdd alias marker absent"

# Negative: legacy top-level selector_mode alias must fail closed.
ERR_LEGACY_TOP="$TMPDIR_LOCAL/legacy-top.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-top.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_legacy_top_alias.json" >/dev/null 2>"$ERR_LEGACY_TOP"
rc_legacy_top="$?"
set -e

[[ "$rc_legacy_top" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010E" "legacy top-level selector_mode alias fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010E" "legacy top-level selector_mode alias unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_FORBIDDEN source=intent.selector_mode" "$ERR_LEGACY_TOP" \
  && pass_case "T-RDD-TRIAGE-MODE-010F" "legacy top-level alias marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010F" "legacy top-level alias marker absent"

# Negative: canonical absent + both legacy aliases must fail closed as source conflict.
ERR_LEGACY_BOTH="$TMPDIR_LOCAL/legacy-both.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_legacy_both_aliases.json" >/dev/null 2>"$ERR_LEGACY_BOTH"
rc_legacy_both="$?"
set -e

[[ "$rc_legacy_both" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010M" "legacy-only dual-alias source conflict fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010M" "legacy-only dual-alias source conflict unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_CONFLICT canonical=<absent> legacy=intent.rdd.selector_mode,intent.selector_mode" "$ERR_LEGACY_BOTH" \
  && pass_case "T-RDD-TRIAGE-MODE-010N" "legacy-only dual-alias source conflict marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010N" "legacy-only dual-alias source conflict marker absent"

# Negative: canonical absent + both legacy aliases with mismatched values must fail closed as source mismatch.
ERR_LEGACY_BOTH_MISMATCH="$TMPDIR_LOCAL/legacy-both-mismatch.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-mismatch.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_legacy_both_aliases_mismatch.json" >/dev/null 2>"$ERR_LEGACY_BOTH_MISMATCH"
rc_legacy_both_mismatch="$?"
set -e

[[ "$rc_legacy_both_mismatch" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010O" "legacy-only dual-alias mismatch fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010O" "legacy-only dual-alias mismatch unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_MISMATCH canonical=<absent> legacy=intent.rdd.selector_mode,intent.selector_mode" "$ERR_LEGACY_BOTH_MISMATCH" \
  && pass_case "T-RDD-TRIAGE-MODE-010P" "legacy-only dual-alias mismatch marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010P" "legacy-only dual-alias mismatch marker absent"

# Negative: canonical absent + both legacy aliases with empty-string value must fail closed as value-invalid.
ERR_LEGACY_BOTH_INVALID_EMPTY="$TMPDIR_LOCAL/legacy-both-invalid-empty.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-invalid-empty.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase15_selector_mode_intent_legacy_both_aliases_invalid_rdd_empty.json" >/dev/null 2>"$ERR_LEGACY_BOTH_INVALID_EMPTY"
rc_legacy_both_invalid_empty="$?"
set -e

[[ "$rc_legacy_both_invalid_empty" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010Q" "legacy-only dual-alias empty-string value fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010Q" "legacy-only dual-alias empty-string value unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_VALUE_INVALID canonical=<absent> legacy=intent.rdd.selector_mode,intent.selector_mode" "$ERR_LEGACY_BOTH_INVALID_EMPTY" \
  && pass_case "T-RDD-TRIAGE-MODE-010R" "legacy-only dual-alias empty-string value-invalid marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010R" "legacy-only dual-alias empty-string value-invalid marker absent"

# Negative: canonical absent + both legacy aliases with non-string value must fail closed as value-invalid.
ERR_LEGACY_BOTH_INVALID_NON_STRING="$TMPDIR_LOCAL/legacy-both-invalid-non-string.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-invalid-non-string.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase15_selector_mode_intent_legacy_both_aliases_invalid_top_non_string.json" >/dev/null 2>"$ERR_LEGACY_BOTH_INVALID_NON_STRING"
rc_legacy_both_invalid_non_string="$?"
set -e

[[ "$rc_legacy_both_invalid_non_string" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010S" "legacy-only dual-alias non-string value fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010S" "legacy-only dual-alias non-string value unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_VALUE_INVALID canonical=<absent> legacy=intent.rdd.selector_mode,intent.selector_mode" "$ERR_LEGACY_BOTH_INVALID_NON_STRING" \
  && pass_case "T-RDD-TRIAGE-MODE-010T" "legacy-only dual-alias non-string value-invalid marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010T" "legacy-only dual-alias non-string value-invalid marker absent"

# Negative: canonical absent + both legacy aliases with equal unsupported non-empty strings must fail closed as value-unsupported.
ERR_LEGACY_BOTH_UNSUPPORTED_EQUAL="$TMPDIR_LOCAL/legacy-both-unsupported-equal.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-unsupported-equal.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase16_selector_mode_intent_legacy_both_aliases_unsupported_equal.json" >/dev/null 2>"$ERR_LEGACY_BOTH_UNSUPPORTED_EQUAL"
rc_legacy_both_unsupported_equal="$?"
set -e

[[ "$rc_legacy_both_unsupported_equal" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010U" "legacy-only dual-alias equal unsupported values fail closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010U" "legacy-only dual-alias equal unsupported values unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_VALUE_UNSUPPORTED canonical=<absent> legacy=intent.rdd.selector_mode,intent.selector_mode" "$ERR_LEGACY_BOTH_UNSUPPORTED_EQUAL" \
  && pass_case "T-RDD-TRIAGE-MODE-010V" "legacy-only dual-alias equal unsupported value marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010V" "legacy-only dual-alias equal unsupported value marker absent"

# Negative: canonical absent + both legacy aliases with mixed allowed/unsupported strings must fail closed as value-unsupported.
ERR_LEGACY_BOTH_UNSUPPORTED_MIXED="$TMPDIR_LOCAL/legacy-both-unsupported-mixed.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-unsupported-mixed.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase16_selector_mode_intent_legacy_both_aliases_unsupported_mixed.json" >/dev/null 2>"$ERR_LEGACY_BOTH_UNSUPPORTED_MIXED"
rc_legacy_both_unsupported_mixed="$?"
set -e

[[ "$rc_legacy_both_unsupported_mixed" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010W" "legacy-only dual-alias mixed allowed/unsupported values fail closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010W" "legacy-only dual-alias mixed allowed/unsupported values unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_VALUE_UNSUPPORTED canonical=<absent> legacy=intent.rdd.selector_mode,intent.selector_mode" "$ERR_LEGACY_BOTH_UNSUPPORTED_MIXED" \
  && pass_case "T-RDD-TRIAGE-MODE-010X" "legacy-only dual-alias mixed unsupported value marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010X" "legacy-only dual-alias mixed unsupported value marker absent"

# Negative: canonical absent + both legacy aliases with equal normalized allowed values must fail closed as source conflict.
ERR_LEGACY_BOTH_NORMALIZED_EQUAL="$TMPDIR_LOCAL/legacy-both-normalized-equal.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-normalized-equal.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase17_selector_mode_intent_legacy_both_aliases_normalized_equal_whitespace.json" >/dev/null 2>"$ERR_LEGACY_BOTH_NORMALIZED_EQUAL"
rc_legacy_both_normalized_equal="$?"
set -e

[[ "$rc_legacy_both_normalized_equal" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010Y" "legacy-only dual-alias equal normalized allowed values fail closed as conflict" \
  || fail_case "T-RDD-TRIAGE-MODE-010Y" "legacy-only dual-alias equal normalized allowed values unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_CONFLICT canonical=<absent> legacy=intent.rdd.selector_mode,intent.selector_mode" "$ERR_LEGACY_BOTH_NORMALIZED_EQUAL" \
  && pass_case "T-RDD-TRIAGE-MODE-010Z" "legacy-only dual-alias normalized-equal conflict marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010Z" "legacy-only dual-alias normalized-equal conflict marker absent"

# Negative: canonical absent + both legacy aliases with different normalized allowed values must fail closed as source mismatch.
ERR_LEGACY_BOTH_NORMALIZED_MISMATCH="$TMPDIR_LOCAL/legacy-both-normalized-mismatch.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-normalized-mismatch.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase17_selector_mode_intent_legacy_both_aliases_normalized_mismatch_whitespace.json" >/dev/null 2>"$ERR_LEGACY_BOTH_NORMALIZED_MISMATCH"
rc_legacy_both_normalized_mismatch="$?"
set -e

[[ "$rc_legacy_both_normalized_mismatch" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-011A" "legacy-only dual-alias different normalized allowed values fail closed as mismatch" \
  || fail_case "T-RDD-TRIAGE-MODE-011A" "legacy-only dual-alias different normalized allowed values unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_MISMATCH canonical=<absent> legacy=intent.rdd.selector_mode,intent.selector_mode" "$ERR_LEGACY_BOTH_NORMALIZED_MISMATCH" \
  && pass_case "T-RDD-TRIAGE-MODE-011B" "legacy-only dual-alias normalized-mismatch marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-011B" "legacy-only dual-alias normalized-mismatch marker absent"

# Negative: canonical absent + both legacy aliases with equal case-normalized allowed values must fail closed as source conflict.
ERR_LEGACY_BOTH_CASE_EQUAL="$TMPDIR_LOCAL/legacy-both-case-equal.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-case-equal.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase18_selector_mode_intent_legacy_both_aliases_case_equal.json" >/dev/null 2>"$ERR_LEGACY_BOTH_CASE_EQUAL"
rc_legacy_both_case_equal="$?"
set -e

[[ "$rc_legacy_both_case_equal" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-011C" "legacy-only dual-alias equal case-normalized allowed values fail closed as conflict" \
  || fail_case "T-RDD-TRIAGE-MODE-011C" "legacy-only dual-alias equal case-normalized allowed values unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_CONFLICT canonical=<absent> legacy=intent.rdd.selector_mode,intent.selector_mode" "$ERR_LEGACY_BOTH_CASE_EQUAL" \
  && pass_case "T-RDD-TRIAGE-MODE-011D" "legacy-only dual-alias case-normalized conflict marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-011D" "legacy-only dual-alias case-normalized conflict marker absent"

# Negative: canonical absent + both legacy aliases with different case-normalized allowed values must fail closed as source mismatch.
ERR_LEGACY_BOTH_CASE_MISMATCH="$TMPDIR_LOCAL/legacy-both-case-mismatch.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-case-mismatch.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase18_selector_mode_intent_legacy_both_aliases_case_mismatch.json" >/dev/null 2>"$ERR_LEGACY_BOTH_CASE_MISMATCH"
rc_legacy_both_case_mismatch="$?"
set -e

[[ "$rc_legacy_both_case_mismatch" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-011E" "legacy-only dual-alias different case-normalized allowed values fail closed as mismatch" \
  || fail_case "T-RDD-TRIAGE-MODE-011E" "legacy-only dual-alias different case-normalized allowed values unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_MISMATCH canonical=<absent> legacy=intent.rdd.selector_mode,intent.selector_mode" "$ERR_LEGACY_BOTH_CASE_MISMATCH" \
  && pass_case "T-RDD-TRIAGE-MODE-011F" "legacy-only dual-alias case-normalized mismatch marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-011F" "legacy-only dual-alias case-normalized mismatch marker absent"

# Negative: canonical + intent.rdd selector_mode must fail closed as source conflict.
ERR_CONFLICT_RDD="$TMPDIR_LOCAL/conflict-rdd.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/conflict-rdd.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_conflict_rdd_alias.json" >/dev/null 2>"$ERR_CONFLICT_RDD"
rc_conflict_rdd="$?"
set -e

[[ "$rc_conflict_rdd" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010G" "canonical+rdd alias source conflict fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010G" "canonical+rdd alias source conflict unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_CONFLICT canonical=intent.constraints.selector_mode legacy=intent.rdd.selector_mode" "$ERR_CONFLICT_RDD" \
  && pass_case "T-RDD-TRIAGE-MODE-010H" "canonical+rdd alias source conflict marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010H" "canonical+rdd alias source conflict marker absent"

# Negative: canonical + top-level selector_mode must fail closed as source conflict.
ERR_CONFLICT_TOP="$TMPDIR_LOCAL/conflict-top.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/conflict-top.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_conflict_top_alias.json" >/dev/null 2>"$ERR_CONFLICT_TOP"
rc_conflict_top="$?"
set -e

[[ "$rc_conflict_top" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010I" "canonical+top alias source conflict fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010I" "canonical+top alias source conflict unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_CONFLICT canonical=intent.constraints.selector_mode legacy=intent.selector_mode" "$ERR_CONFLICT_TOP" \
  && pass_case "T-RDD-TRIAGE-MODE-010J" "canonical+top alias source conflict marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010J" "canonical+top alias source conflict marker absent"

# Negative: canonical + both aliases must fail closed as source conflict.
ERR_CONFLICT_BOTH="$TMPDIR_LOCAL/conflict-both.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/conflict-both.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_conflict_both_aliases.json" >/dev/null 2>"$ERR_CONFLICT_BOTH"
rc_conflict_both="$?"
set -e

[[ "$rc_conflict_both" -ne 0 ]] \
  && pass_case "T-RDD-TRIAGE-MODE-010K" "canonical+both aliases source conflict fails closed" \
  || fail_case "T-RDD-TRIAGE-MODE-010K" "canonical+both aliases source conflict unexpectedly succeeded"

grep -q "RDD_TRIAGE_SELECTOR_MODE_SOURCE_CONFLICT canonical=intent.constraints.selector_mode legacy=intent.rdd.selector_mode,intent.selector_mode" "$ERR_CONFLICT_BOTH" \
  && pass_case "T-RDD-TRIAGE-MODE-010L" "canonical+both aliases source conflict marker present" \
  || fail_case "T-RDD-TRIAGE-MODE-010L" "canonical+both aliases source conflict marker absent"

# Determinism: normalize explicit positive output and negative markers across two runs.
OUT_EXPLICIT_2="$TMPDIR_LOCAL/explicit-2.record.json"
ERR_EXPLICIT_2="$TMPDIR_LOCAL/explicit-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/explicit-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_explicit.json" >"$OUT_EXPLICIT_2" 2>"$ERR_EXPLICIT_2"
rc_explicit_2="$?"
set -e
[[ "$rc_explicit_2" -eq 0 ]] || fail_case "T-RDD-TRIAGE-MODE-011" "explicit run2 failed ($rc_explicit_2)"

ERR_MISSING_MAP_2="$TMPDIR_LOCAL/missing-map-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_missing_map.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/missing-map-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_explicit.json" >/dev/null 2>"$ERR_MISSING_MAP_2"
set -e

ERR_INVALID_MAP_2="$TMPDIR_LOCAL/invalid-map-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_invalid_map_type.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/invalid-map-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_explicit.json" >/dev/null 2>"$ERR_INVALID_MAP_2"
set -e

ERR_CASE_EXPLICIT_2="$TMPDIR_LOCAL/case-explicit-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/case-explicit-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase19_selector_mode_intent_canonical_case_explicit.json" >/dev/null 2>"$ERR_CASE_EXPLICIT_2"
set -e

ERR_CASE_COMPAT_2="$TMPDIR_LOCAL/case-compat-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_legacy_single_case.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/case-compat-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase19_selector_mode_intent_canonical_case_compat.json" >/dev/null 2>"$ERR_CASE_COMPAT_2"
set -e

ERR_INVALID_REQUEST_MODE_NON_STRING_2="$TMPDIR_LOCAL/invalid-request-mode-non-string-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/invalid-request-mode-non-string-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase20_selector_mode_intent_canonical_non_string.json" >/dev/null 2>"$ERR_INVALID_REQUEST_MODE_NON_STRING_2"
set -e

ERR_INVALID_REQUEST_MODE_EMPTY_2="$TMPDIR_LOCAL/invalid-request-mode-empty-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/invalid-request-mode-empty-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase20_selector_mode_intent_canonical_empty_string.json" >/dev/null 2>"$ERR_INVALID_REQUEST_MODE_EMPTY_2"
set -e

ERR_INVALID_CANONICAL_WITH_LEGACY_BOTH_2="$TMPDIR_LOCAL/invalid-canonical-with-legacy-both-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/invalid-canonical-with-legacy-both-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase20_selector_mode_intent_canonical_invalid_with_legacy_both_aliases.json" >/dev/null 2>"$ERR_INVALID_CANONICAL_WITH_LEGACY_BOTH_2"
set -e

ERR_LEGACY_RDD_2="$TMPDIR_LOCAL/legacy-rdd-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-rdd-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_legacy_rdd_alias.json" >/dev/null 2>"$ERR_LEGACY_RDD_2"
set -e

ERR_LEGACY_TOP_2="$TMPDIR_LOCAL/legacy-top-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-top-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_legacy_top_alias.json" >/dev/null 2>"$ERR_LEGACY_TOP_2"
set -e

ERR_LEGACY_BOTH_2="$TMPDIR_LOCAL/legacy-both-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_legacy_both_aliases.json" >/dev/null 2>"$ERR_LEGACY_BOTH_2"
set -e

ERR_LEGACY_BOTH_MISMATCH_2="$TMPDIR_LOCAL/legacy-both-mismatch-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-mismatch-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_legacy_both_aliases_mismatch.json" >/dev/null 2>"$ERR_LEGACY_BOTH_MISMATCH_2"
set -e

ERR_LEGACY_BOTH_INVALID_EMPTY_2="$TMPDIR_LOCAL/legacy-both-invalid-empty-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-invalid-empty-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase15_selector_mode_intent_legacy_both_aliases_invalid_rdd_empty.json" >/dev/null 2>"$ERR_LEGACY_BOTH_INVALID_EMPTY_2"
set -e

ERR_LEGACY_BOTH_INVALID_NON_STRING_2="$TMPDIR_LOCAL/legacy-both-invalid-non-string-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-invalid-non-string-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase15_selector_mode_intent_legacy_both_aliases_invalid_top_non_string.json" >/dev/null 2>"$ERR_LEGACY_BOTH_INVALID_NON_STRING_2"
set -e

ERR_LEGACY_BOTH_UNSUPPORTED_EQUAL_2="$TMPDIR_LOCAL/legacy-both-unsupported-equal-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-unsupported-equal-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase16_selector_mode_intent_legacy_both_aliases_unsupported_equal.json" >/dev/null 2>"$ERR_LEGACY_BOTH_UNSUPPORTED_EQUAL_2"
set -e

ERR_LEGACY_BOTH_UNSUPPORTED_MIXED_2="$TMPDIR_LOCAL/legacy-both-unsupported-mixed-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-unsupported-mixed-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase16_selector_mode_intent_legacy_both_aliases_unsupported_mixed.json" >/dev/null 2>"$ERR_LEGACY_BOTH_UNSUPPORTED_MIXED_2"
set -e

ERR_LEGACY_BOTH_NORMALIZED_EQUAL_2="$TMPDIR_LOCAL/legacy-both-normalized-equal-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-normalized-equal-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase17_selector_mode_intent_legacy_both_aliases_normalized_equal_whitespace.json" >/dev/null 2>"$ERR_LEGACY_BOTH_NORMALIZED_EQUAL_2"
set -e

ERR_LEGACY_BOTH_NORMALIZED_MISMATCH_2="$TMPDIR_LOCAL/legacy-both-normalized-mismatch-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-normalized-mismatch-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase17_selector_mode_intent_legacy_both_aliases_normalized_mismatch_whitespace.json" >/dev/null 2>"$ERR_LEGACY_BOTH_NORMALIZED_MISMATCH_2"
set -e

ERR_LEGACY_BOTH_CASE_EQUAL_2="$TMPDIR_LOCAL/legacy-both-case-equal-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-case-equal-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase18_selector_mode_intent_legacy_both_aliases_case_equal.json" >/dev/null 2>"$ERR_LEGACY_BOTH_CASE_EQUAL_2"
set -e

ERR_LEGACY_BOTH_CASE_MISMATCH_2="$TMPDIR_LOCAL/legacy-both-case-mismatch-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/legacy-both-case-mismatch-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase18_selector_mode_intent_legacy_both_aliases_case_mismatch.json" >/dev/null 2>"$ERR_LEGACY_BOTH_CASE_MISMATCH_2"
set -e

ERR_CONFLICT_RDD_2="$TMPDIR_LOCAL/conflict-rdd-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/conflict-rdd-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_conflict_rdd_alias.json" >/dev/null 2>"$ERR_CONFLICT_RDD_2"
set -e

ERR_CONFLICT_TOP_2="$TMPDIR_LOCAL/conflict-top-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/conflict-top-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_conflict_top_alias.json" >/dev/null 2>"$ERR_CONFLICT_TOP_2"
set -e

ERR_CONFLICT_BOTH_2="$TMPDIR_LOCAL/conflict-both-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/conflict-both-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase14_selector_mode_intent_conflict_both_aliases.json" >/dev/null 2>"$ERR_CONFLICT_BOTH_2"
set -e

HASH_1="$(python3 - <<'PY' "$OUT_EXPLICIT" "$ERR_MISSING_MAP" "$ERR_INVALID_MAP" "$ERR_INVALID_REQUEST_MODE" "$ERR_CASE_EXPLICIT" "$ERR_CASE_COMPAT" "$ERR_INVALID_REQUEST_MODE_NON_STRING" "$ERR_INVALID_REQUEST_MODE_EMPTY" "$ERR_INVALID_CANONICAL_WITH_LEGACY_BOTH" "$ERR_LEGACY_RDD" "$ERR_LEGACY_TOP" "$ERR_LEGACY_BOTH" "$ERR_LEGACY_BOTH_MISMATCH" "$ERR_LEGACY_BOTH_INVALID_EMPTY" "$ERR_LEGACY_BOTH_INVALID_NON_STRING" "$ERR_LEGACY_BOTH_UNSUPPORTED_EQUAL" "$ERR_LEGACY_BOTH_UNSUPPORTED_MIXED" "$ERR_LEGACY_BOTH_NORMALIZED_EQUAL" "$ERR_LEGACY_BOTH_NORMALIZED_MISMATCH" "$ERR_LEGACY_BOTH_CASE_EQUAL" "$ERR_LEGACY_BOTH_CASE_MISMATCH" "$ERR_CONFLICT_RDD" "$ERR_CONFLICT_TOP" "$ERR_CONFLICT_BOTH"
import hashlib, json, sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
for k in ("timestamp_utc","session_id","request_id","process_id","prev_record_hash","record_hash","signature","signing_key_id","request_bytes_b64"):
    obj.pop(k, None)
payload = {
    "explicit_normalized": obj,
    "missing_map_marker": open(sys.argv[2], encoding='utf-8').read().strip(),
    "invalid_map_marker": open(sys.argv[3], encoding='utf-8').read().strip(),
    "invalid_request_mode_marker": open(sys.argv[4], encoding='utf-8').read().strip(),
    "canonical_case_explicit_marker": open(sys.argv[5], encoding='utf-8').read().strip(),
    "canonical_case_compat_marker": open(sys.argv[6], encoding='utf-8').read().strip(),
    "invalid_request_mode_non_string_marker": open(sys.argv[7], encoding='utf-8').read().strip(),
    "invalid_request_mode_empty_marker": open(sys.argv[8], encoding='utf-8').read().strip(),
    "invalid_canonical_with_legacy_both_marker": open(sys.argv[9], encoding='utf-8').read().strip(),
    "legacy_rdd_alias_marker": open(sys.argv[10], encoding='utf-8').read().strip(),
    "legacy_top_alias_marker": open(sys.argv[11], encoding='utf-8').read().strip(),
    "legacy_both_aliases_marker": open(sys.argv[12], encoding='utf-8').read().strip(),
    "legacy_both_aliases_mismatch_marker": open(sys.argv[13], encoding='utf-8').read().strip(),
    "legacy_both_aliases_invalid_empty_marker": open(sys.argv[14], encoding='utf-8').read().strip(),
    "legacy_both_aliases_invalid_non_string_marker": open(sys.argv[15], encoding='utf-8').read().strip(),
    "legacy_both_aliases_unsupported_equal_marker": open(sys.argv[16], encoding='utf-8').read().strip(),
    "legacy_both_aliases_unsupported_mixed_marker": open(sys.argv[17], encoding='utf-8').read().strip(),
    "legacy_both_aliases_normalized_equal_marker": open(sys.argv[18], encoding='utf-8').read().strip(),
    "legacy_both_aliases_normalized_mismatch_marker": open(sys.argv[19], encoding='utf-8').read().strip(),
    "legacy_both_aliases_case_equal_marker": open(sys.argv[20], encoding='utf-8').read().strip(),
    "legacy_both_aliases_case_mismatch_marker": open(sys.argv[21], encoding='utf-8').read().strip(),
    "conflict_rdd_alias_marker": open(sys.argv[22], encoding='utf-8').read().strip(),
    "conflict_top_alias_marker": open(sys.argv[23], encoding='utf-8').read().strip(),
    "conflict_both_aliases_marker": open(sys.argv[24], encoding='utf-8').read().strip(),
}
print(hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode('utf-8')).hexdigest())
PY
)"

ERR_INVALID_REQUEST_MODE_2="$TMPDIR_LOCAL/invalid-request-mode-2.stderr.txt"
set +e
GOV_TRIAGE_CRITERIA_PATH="$FIXTURES/rdd_phase14_selector_mode_criteria_explicit_valid.json" \
GOV_DECISION_CHAIN_PATH="$TMPDIR_LOCAL/invalid-request-mode-2.chain.jsonl" \
"$PASS_TRIAGE" "$FIXTURES/rdd_phase19_selector_mode_intent_canonical_case_invalid.json" >/dev/null 2>"$ERR_INVALID_REQUEST_MODE_2"
set -e

HASH_2="$(python3 - <<'PY' "$OUT_EXPLICIT_2" "$ERR_MISSING_MAP_2" "$ERR_INVALID_MAP_2" "$ERR_INVALID_REQUEST_MODE_2" "$ERR_CASE_EXPLICIT_2" "$ERR_CASE_COMPAT_2" "$ERR_INVALID_REQUEST_MODE_NON_STRING_2" "$ERR_INVALID_REQUEST_MODE_EMPTY_2" "$ERR_INVALID_CANONICAL_WITH_LEGACY_BOTH_2" "$ERR_LEGACY_RDD_2" "$ERR_LEGACY_TOP_2" "$ERR_LEGACY_BOTH_2" "$ERR_LEGACY_BOTH_MISMATCH_2" "$ERR_LEGACY_BOTH_INVALID_EMPTY_2" "$ERR_LEGACY_BOTH_INVALID_NON_STRING_2" "$ERR_LEGACY_BOTH_UNSUPPORTED_EQUAL_2" "$ERR_LEGACY_BOTH_UNSUPPORTED_MIXED_2" "$ERR_LEGACY_BOTH_NORMALIZED_EQUAL_2" "$ERR_LEGACY_BOTH_NORMALIZED_MISMATCH_2" "$ERR_LEGACY_BOTH_CASE_EQUAL_2" "$ERR_LEGACY_BOTH_CASE_MISMATCH_2" "$ERR_CONFLICT_RDD_2" "$ERR_CONFLICT_TOP_2" "$ERR_CONFLICT_BOTH_2"
import hashlib, json, sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
for k in ("timestamp_utc","session_id","request_id","process_id","prev_record_hash","record_hash","signature","signing_key_id","request_bytes_b64"):
    obj.pop(k, None)
payload = {
    "explicit_normalized": obj,
    "missing_map_marker": open(sys.argv[2], encoding='utf-8').read().strip(),
    "invalid_map_marker": open(sys.argv[3], encoding='utf-8').read().strip(),
    "invalid_request_mode_marker": open(sys.argv[4], encoding='utf-8').read().strip(),
    "canonical_case_explicit_marker": open(sys.argv[5], encoding='utf-8').read().strip(),
    "canonical_case_compat_marker": open(sys.argv[6], encoding='utf-8').read().strip(),
    "invalid_request_mode_non_string_marker": open(sys.argv[7], encoding='utf-8').read().strip(),
    "invalid_request_mode_empty_marker": open(sys.argv[8], encoding='utf-8').read().strip(),
    "invalid_canonical_with_legacy_both_marker": open(sys.argv[9], encoding='utf-8').read().strip(),
    "legacy_rdd_alias_marker": open(sys.argv[10], encoding='utf-8').read().strip(),
    "legacy_top_alias_marker": open(sys.argv[11], encoding='utf-8').read().strip(),
    "legacy_both_aliases_marker": open(sys.argv[12], encoding='utf-8').read().strip(),
    "legacy_both_aliases_mismatch_marker": open(sys.argv[13], encoding='utf-8').read().strip(),
    "legacy_both_aliases_invalid_empty_marker": open(sys.argv[14], encoding='utf-8').read().strip(),
    "legacy_both_aliases_invalid_non_string_marker": open(sys.argv[15], encoding='utf-8').read().strip(),
    "legacy_both_aliases_unsupported_equal_marker": open(sys.argv[16], encoding='utf-8').read().strip(),
    "legacy_both_aliases_unsupported_mixed_marker": open(sys.argv[17], encoding='utf-8').read().strip(),
    "legacy_both_aliases_normalized_equal_marker": open(sys.argv[18], encoding='utf-8').read().strip(),
    "legacy_both_aliases_normalized_mismatch_marker": open(sys.argv[19], encoding='utf-8').read().strip(),
    "legacy_both_aliases_case_equal_marker": open(sys.argv[20], encoding='utf-8').read().strip(),
    "legacy_both_aliases_case_mismatch_marker": open(sys.argv[21], encoding='utf-8').read().strip(),
    "conflict_rdd_alias_marker": open(sys.argv[22], encoding='utf-8').read().strip(),
    "conflict_top_alias_marker": open(sys.argv[23], encoding='utf-8').read().strip(),
    "conflict_both_aliases_marker": open(sys.argv[24], encoding='utf-8').read().strip(),
}
print(hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode('utf-8')).hexdigest())
PY
)"

echo "SELECTOR_MODE_MATRIX_HASH_1=$HASH_1"
echo "SELECTOR_MODE_MATRIX_HASH_2=$HASH_2"
[[ "$HASH_1" == "$HASH_2" ]] \
  && pass_case "T-RDD-TRIAGE-MODE-012" "selector-mode matrix deterministic hash match" \
  || fail_case "T-RDD-TRIAGE-MODE-012" "selector-mode matrix deterministic hash mismatch"

echo "PASS: $pass  FAIL: $fail"
if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
