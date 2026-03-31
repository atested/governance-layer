#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

run_all_cases() {
run_case pass 0 YES NO NONE
run_case non_admissible 1 NO NO AAT_C1_CONTRADICTION
run_case hard_stop 2 NO YES AAT_K1_PHANTOM_ACTION
run_case schema_invalid 2 NO YES AAT_GATE_B_TYPED_REF_TYPE_MISSING:action_decision_record --typed-ref-catalog system/tests/fixtures/aat_gate_b/schema_invalid/typed_ref_catalog_missing_action_decision_record.json

echo "AAT_GATE_B_TEST=PASS"
}

run_case() {
  local case_name="$1"
  local expected_exit="$2"
  local expected_adm="$3"
  local expected_stop="$4"
  local expected_reason="$5"
  shift 5
  local extra=("$@")
  local fdir="system/tests/fixtures/aat_gate_b/$case_name"
  : > "$fdir/ledger.jsonl"

  local -a cmd=(
    system/scripts/aat-gate-b-append.sh
    --ledger "$fdir/ledger.jsonl"
    --aat-action-record "$fdir/action_record.json"
    --decision-record "$fdir/decision_record.json"
    --proof-bundle-manifest "$fdir/proof_manifest.json"
    --rules-snapshot "$fdir/rules.json"
    --operation-id "aat-$case_name"
  )
  if ((${#extra[@]} > 0)); then
    cmd+=("${extra[@]}")
  fi

  set +e
  out="$("${cmd[@]}" 2>&1)"
  rc=$?
  set -e

  norm="$(printf '%s\n' "$out" | system/tests/normalize_aat_gate_b_output.sh)"
  printf 'CASE=%s\nEXIT_CODE=%s\n%s\n' "$case_name" "$rc" "$norm"

  [[ "$rc" -eq "$expected_exit" ]]
  printf '%s\n' "$norm" | rg "^ADMISSIBLE=$expected_adm$" >/dev/null
  printf '%s\n' "$norm" | rg "^STOP_REQUIRED=$expected_stop$" >/dev/null
  printf '%s\n' "$norm" | rg "^REASON_CODE=$expected_reason$" >/dev/null

  if [[ "$case_name" != "schema_invalid" ]]; then
    [[ "$(wc -l < "$fdir/ledger.jsonl" | tr -d ' ')" -eq 2 ]]
    verify_out="$(python3 scripts/foundation_v0_process_ledger.py verify --ledger "$fdir/ledger.jsonl" --artifact-dir "$fdir")"
    printf '%s\n' "$verify_out" | rg '^VERIFY_STATUS=' >/dev/null
  fi
}

if [[ "${1:-}" == "--single-run" ]]; then
  run_all_cases
  exit 0
fi

tmp1="$(mktemp)"
tmp2="$(mktemp)"
trap 'rm -f "$tmp1" "$tmp2"' EXIT

bash "$0" --single-run > "$tmp1" 2>&1
bash "$0" --single-run > "$tmp2" 2>&1
cat "$tmp1"
sha1="$(shasum -a 256 "$tmp1" | awk '{print $1}')"
sha2="$(shasum -a 256 "$tmp2" | awk '{print $1}')"
printf 'RUN1_SHA256=%s\nRUN2_SHA256=%s\n' "$sha1" "$sha2"
[[ "$sha1" == "$sha2" ]]
echo "DETERMINISTIC=YES"
