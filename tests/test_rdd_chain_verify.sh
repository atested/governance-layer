#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERIFY="$ROOT/scripts/verify-chain.py"
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
  local id="$1" file="$2" expected_rc="$3" expected_substr="${4:-}"
  local out
  out="$(mktemp "${TMPDIR:-/tmp}/rdd-chain-verify.XXXXXX")"
  set +e
  python3 "$VERIFY" "$file" >"$out" 2>&1
  local rc=$?
  set -e
  if [[ "$rc" != "$expected_rc" ]]; then
    fail_case "$id" "unexpected rc=$rc expected=$expected_rc"
    cat "$out"
    rm -f "$out"
    return
  fi
  if [[ -n "$expected_substr" ]] && ! grep -Fq "$expected_substr" "$out"; then
    fail_case "$id" "missing expected output: $expected_substr"
    cat "$out"
    rm -f "$out"
    return
  fi
  pass_case "$id" "rc=$rc"
  rm -f "$out"
}

run_matrix_once() {
  local outfile="$2"
  : >"$outfile"

  {
    echo "[MATRIX] positive and compatibility checks"
    python3 "$VERIFY" "$FIX/rdd_chain_phase3_valid.jsonl"
    python3 "$VERIFY" "$FIX/rdd_chain_phase3_legacy_compat.jsonl"
  } >>"$outfile" 2>&1

  {
    echo "[MATRIX] negatives"
    python3 "$VERIFY" "$FIX/rdd_chain_phase3_invalid_triage_before_pass.jsonl" || true
    python3 "$VERIFY" "$FIX/rdd_chain_phase3_invalid_terminal_before_triage.jsonl" || true
    python3 "$VERIFY" "$FIX/rdd_chain_phase3_invalid_triage_refs_non_undecided_pass.jsonl" || true
    python3 "$VERIFY" "$FIX/rdd_chain_phase3_invalid_pass_backlink.jsonl" || true
    python3 "$VERIFY" "$FIX/rdd_chain_phase3_invalid_duplicate_triage.jsonl" || true
  } >>"$outfile" 2>&1
}

run_expect "T-RDD-CHAIN-001" "$FIX/rdd_chain_phase3_valid.jsonl" "0" "PASS: chain verified (2 records)"
run_expect "T-RDD-CHAIN-002" "$FIX/rdd_chain_phase3_legacy_compat.jsonl" "0" "PASS: chain verified (2 records)"
run_expect "T-RDD-CHAIN-003" "$FIX/rdd_chain_phase3_invalid_triage_before_pass.jsonl" "1" "triage_decision appears before pass_decision"
run_expect "T-RDD-CHAIN-004" "$FIX/rdd_chain_phase3_invalid_terminal_before_triage.jsonl" "1" "terminal_judgment appears before triage_decision"
run_expect "T-RDD-CHAIN-005" "$FIX/rdd_chain_phase3_invalid_triage_refs_non_undecided_pass.jsonl" "1" "triage_decision references non-UNDECIDED pass record"
run_expect "T-RDD-CHAIN-006" "$FIX/rdd_chain_phase3_invalid_pass_backlink.jsonl" "1" "pass_decision contains forbidden backward-link field"
run_expect "T-RDD-CHAIN-007" "$FIX/rdd_chain_phase3_invalid_duplicate_triage.jsonl" "1" "duplicate triage_decision"

run1="$(mktemp "${TMPDIR:-/tmp}/rdd-chain-run1.XXXXXX")"
run2="$(mktemp "${TMPDIR:-/tmp}/rdd-chain-run2.XXXXXX")"
trap 'rm -f "$run1" "$run2"' EXIT

run_matrix_once "RUN1" "$run1"
run_matrix_once "RUN2" "$run2"

h1="$(sha256sum "$run1" | awk '{print $1}')"
h2="$(sha256sum "$run2" | awk '{print $1}')"
echo "DETERMINISM_RUN1_HASH=$h1"
echo "DETERMINISM_RUN2_HASH=$h2"
if [[ "$h1" == "$h2" ]]; then
  pass_case "T-RDD-CHAIN-008" "deterministic matrix output"
else
  fail_case "T-RDD-CHAIN-008" "determinism hash mismatch"
fi

echo "PASS: $pass  FAIL: $fail"
if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
