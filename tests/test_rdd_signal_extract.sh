#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTRACT="$ROOT/scripts/extract-rdd-signals.py"
FIX="$ROOT/tests/fixtures"

pass=0
fail=0

pass_case() {
  local id="$1" msg="$2"
  echo "PASS: $id $msg"
  pass=$((pass+1))
}

fail_case() {
  local id="$1" msg="$2"
  echo "FAIL: $id $msg"
  fail=$((fail+1))
}

run_expect() {
  local id="$1" chain="$2" expected_rc="$3" expected_substr="${4:-}"
  local out out_json
  out="$(mktemp "${TMPDIR:-/tmp}/rdd-signal-extract.XXXXXX")"
  out_json="$(mktemp "${TMPDIR:-/tmp}/rdd-signal-out.XXXXXX")"
  set +e
  python3 "$EXTRACT" "$chain" --out "$out_json" >"$out" 2>&1
  local rc=$?
  set -e
  if [[ "$rc" != "$expected_rc" ]]; then
    fail_case "$id" "unexpected rc=$rc expected=$expected_rc"
    cat "$out"
    rm -f "$out" "$out_json"
    return
  fi
  if [[ -n "$expected_substr" ]] && ! grep -Fq "$expected_substr" "$out"; then
    fail_case "$id" "missing expected output: $expected_substr"
    cat "$out"
    rm -f "$out" "$out_json"
    return
  fi
  pass_case "$id" "rc=$rc"
  rm -f "$out" "$out_json"
}

run_expect "T-RDD-SIGNAL-001" "$FIX/rdd_chain_phase4_valid_signals.jsonl" "0" "PASS: extracted 2 structural signals"

valid_out="$(mktemp "${TMPDIR:-/tmp}/rdd-signal-valid.XXXXXX")"
python3 "$EXTRACT" "$FIX/rdd_chain_phase4_valid_signals.jsonl" --out "$valid_out" >/dev/null
python3 - "$valid_out" <<'PY'
import json, sys
path = sys.argv[1]
obj = json.load(open(path, "r", encoding="utf-8"))
assert obj["signal_index_version"] == "rdd_signal_index.v1"
signals = obj["signals"]
assert len(signals) == 2
assert signals[0]["signal_id"] == "S1"
assert signals[1]["signal_id"] == "S2"
for s in signals:
    assert set(["signal_id", "deficiency_class", "surface", "description", "case_ref"]).issubset(s.keys())
PY
pass_case "T-RDD-SIGNAL-002" "flattened output schema + deterministic ordering"
rm -f "$valid_out"

run_expect "T-RDD-SIGNAL-003" "$FIX/rdd_chain_phase4_non_triage_only.jsonl" "0" "PASS: extracted 0 structural signals"
run_expect "T-RDD-SIGNAL-004" "$FIX/rdd_chain_phase4_triage_no_signals.jsonl" "0" "PASS: extracted 0 structural signals"
run_expect "T-RDD-SIGNAL-005" "$FIX/rdd_chain_phase4_malformed_signal_missing_id.jsonl" "1" "missing required field 'id'"

run1_json="$(mktemp "${TMPDIR:-/tmp}/rdd-signal-run1.XXXXXX")"
run2_json="$(mktemp "${TMPDIR:-/tmp}/rdd-signal-run2.XXXXXX")"
python3 "$EXTRACT" "$FIX/rdd_chain_phase4_valid_signals.jsonl" --out "$run1_json" >/dev/null
python3 "$EXTRACT" "$FIX/rdd_chain_phase4_valid_signals.jsonl" --out "$run2_json" >/dev/null
h1="$(sha256sum "$run1_json" | awk '{print $1}')"
h2="$(sha256sum "$run2_json" | awk '{print $1}')"
echo "DETERMINISM_RUN1_HASH=$h1"
echo "DETERMINISM_RUN2_HASH=$h2"
if [[ "$h1" == "$h2" ]]; then
  pass_case "T-RDD-SIGNAL-006" "deterministic output hash across identical runs"
else
  fail_case "T-RDD-SIGNAL-006" "deterministic output hash mismatch"
fi

stable_out="$ROOT/out/rdd/signal-index.json"
python3 "$EXTRACT" "$FIX/rdd_chain_phase4_valid_signals.jsonl" --out "$stable_out" >/dev/null
h3="$(sha256sum "$stable_out" | awk '{print $1}')"
python3 "$EXTRACT" "$FIX/rdd_chain_phase4_valid_signals.jsonl" --out "$stable_out" >/dev/null
h4="$(sha256sum "$stable_out" | awk '{print $1}')"
echo "IDEMPOTENCY_RUN1_HASH=$h3"
echo "IDEMPOTENCY_RUN2_HASH=$h4"
if [[ "$h3" == "$h4" ]]; then
  pass_case "T-RDD-SIGNAL-007" "idempotent repeated writes preserve bytes"
else
  fail_case "T-RDD-SIGNAL-007" "idempotent write hash mismatch"
fi

echo "PASS: $pass  FAIL: $fail"
if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
