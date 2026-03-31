#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER="$ROOT/scripts/run_validate_proof_bundle_with_aat_shim.sh"

assert_eq() {
  local got="$1"
  local want="$2"
  local label="$3"
  [[ "$got" == "$want" ]] || { echo "FAIL:$label expected=$want got=$got"; exit 1; }
}

run_once() {
  local text out
  text=$'AAT_SHIM_INPUTS=FOUND path=aat\nAAT_SHIM_RESULT=HARD_STOP REASON_CODE=RC-FS-TEST LEDGER_APPENDED=NO\n'
  out="$(bash "$WRAPPER" --_extract-stop-code "$text")"
  assert_eq "$out" "RC-FS-TEST" "anchored_reason_code"

  text=$'AAT_SHIM_INPUTS=FOUND path=aat\nAAT_SHIM_RESULT=HARD_STOP LEDGER_APPENDED=NO\nAAT_SHIM_REASON=AAT_STOP_ANCHORED\n'
  out="$(bash "$WRAPPER" --_extract-stop-code "$text")"
  assert_eq "$out" "AAT_STOP_ANCHORED" "anchored_shim_reason"

  text=$'AAT_SHIM_INPUTS=FOUND path=aat\nAAT_SHIM_RESULT=HARD_STOP LEDGER_APPENDED=NO\n'
  out="$(bash "$WRAPPER" --_extract-stop-code "$text")"
  assert_eq "$out" "UNKNOWN" "no_keyed_reason"

  echo "CASE=STOP_CODE_REASON_SOURCE PASS"
}

main() {
  local r1 r2 h1 h2
  r1="$(mktemp)"
  r2="$(mktemp)"
  run_once >"$r1"
  run_once >"$r2"
  h1="$(shasum -a 256 "$r1" | awk '{print $1}')"
  h2="$(shasum -a 256 "$r2" | awk '{print $1}')"
  cat "$r1"
  echo "RUN1_SHA256=$h1"
  echo "RUN2_SHA256=$h2"
  [[ "$h1" == "$h2" ]] || { echo "DETERMINISTIC=NO"; exit 1; }
  echo "DETERMINISTIC=YES"
  rm -f "$r1" "$r2"
}

main "$@"
