#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

run_case() {
  local case_name="$1"
  local expected_exit="$2"
  local expected_status="$3"
  local expected_reason="$4"
  local expected_appended="$5"

  local fixture_dir="system/tests/fixtures/aat_gate_c/$case_name"
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  cp "$fixture_dir"/*.json "$tmp_dir"/
  : > "$tmp_dir/ledger.jsonl"

  set +e
  local out
  out="$(system/scripts/aat-gate-c-wrapper.sh \
    --action-record "$tmp_dir/action_record.json" \
    --decision-record "$tmp_dir/decision_record.json" \
    --ledger "$tmp_dir/ledger.jsonl" 2>&1)"
  local rc=$?
  set -e

  local norm
  norm="$(printf '%s\n' "$out" | system/scripts/aat-gate-c-normalize.sh)"
  printf 'CASE=%s\nEXIT_CODE=%s\n%s\n' "$case_name" "$rc" "$norm"

  [[ "$rc" -eq "$expected_exit" ]]
  printf '%s\n' "$norm" | rg "^STATUS=$expected_status$" >/dev/null
  printf '%s\n' "$norm" | rg "^REASON_CODE=$expected_reason$" >/dev/null
  printf '%s\n' "$norm" | rg "^LEDGER_APPENDED=$expected_appended$" >/dev/null

  if [[ "$expected_appended" == "YES" ]]; then
    [[ "$(wc -l < "$tmp_dir/ledger.jsonl" | tr -d ' ')" -eq 2 ]]
  fi

  rm -rf "$tmp_dir"
}

run_all() {
  run_case pass 0 PASS NONE YES
  run_case non_admissible 10 NON_ADMISSIBLE AAT_C1_CONTRADICTION YES
  run_case hard_stop 20 HARD_STOP AAT_K1_PHANTOM_ACTION NO
  echo "AAT_GATE_C_TEST=PASS"
}

if [[ "${1:-}" == "--single-run" ]]; then
  run_all
  exit 0
fi

log1="$(mktemp)"
log2="$(mktemp)"
trap 'rm -f "$log1" "$log2"' EXIT

bash "$0" --single-run > "$log1" 2>&1
bash "$0" --single-run > "$log2" 2>&1

cat "$log1"
sha1="$(shasum -a 256 "$log1" | awk '{print $1}')"
sha2="$(shasum -a 256 "$log2" | awk '{print $1}')"
printf 'RUN1_SHA256=%s\nRUN2_SHA256=%s\n' "$sha1" "$sha2"
[[ "$sha1" == "$sha2" ]]
echo "DETERMINISTIC=YES"
