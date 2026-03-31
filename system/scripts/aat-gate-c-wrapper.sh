#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

action_record=""
decision_record=""
ledger=""

usage() {
  cat <<'USAGE'
usage: system/scripts/aat-gate-c-wrapper.sh --action-record <path> --decision-record <path> --ledger <path>
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --action-record) action_record="$2"; shift 2 ;;
    --decision-record) decision_record="$2"; shift 2 ;;
    --ledger) ledger="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "STATUS=HARD_STOP"; echo "REASON_CODE=AAT_GATE_C_BAD_ARGS"; echo "LEDGER_APPENDED=NO"; exit 20 ;;
  esac
done

[[ -n "$action_record" && -f "$action_record" ]] || { echo "STATUS=HARD_STOP"; echo "REASON_CODE=AAT_GATE_C_ACTION_RECORD_MISSING"; echo "LEDGER_APPENDED=NO"; exit 20; }
[[ -n "$decision_record" && -f "$decision_record" ]] || { echo "STATUS=HARD_STOP"; echo "REASON_CODE=AAT_GATE_C_DECISION_RECORD_MISSING"; echo "LEDGER_APPENDED=NO"; exit 20; }
[[ -n "$ledger" ]] || { echo "STATUS=HARD_STOP"; echo "REASON_CODE=AAT_GATE_C_LEDGER_ARG_MISSING"; echo "LEDGER_APPENDED=NO"; exit 20; }

bundle_dir="$(cd "$(dirname "$action_record")" && pwd)"
proof_manifest="$bundle_dir/proof_manifest.json"
rules_snapshot="$bundle_dir/rules.json"

[[ -f "$proof_manifest" ]] || { echo "STATUS=HARD_STOP"; echo "REASON_CODE=AAT_GATE_C_PROOF_MANIFEST_MISSING"; echo "LEDGER_APPENDED=NO"; exit 20; }
[[ -f "$rules_snapshot" ]] || { echo "STATUS=HARD_STOP"; echo "REASON_CODE=AAT_GATE_C_RULES_SNAPSHOT_MISSING"; echo "LEDGER_APPENDED=NO"; exit 20; }

a_out="$(system/scripts/aat-admissibility-gate.sh --action-bundle-dir "$bundle_dir" 2>&1 || true)"
a_stop="$(printf '%s\n' "$a_out" | rg -m1 '^STOP_REQUIRED=' | cut -d= -f2- || true)"
a_reason="$(printf '%s\n' "$a_out" | rg -m1 '^REASON_CODE=' | cut -d= -f2- || true)"

if [[ "$a_stop" == "YES" ]]; then
  echo "STATUS=HARD_STOP"
  echo "REASON_CODE=${a_reason:-AAT_GATE_C_GATE_A_HARD_STOP}"
  echo "LEDGER_APPENDED=NO"
  exit 20
fi

b_out="$(system/scripts/aat-gate-b-append.sh \
  --ledger "$ledger" \
  --aat-action-record "$action_record" \
  --decision-record "$decision_record" \
  --proof-bundle-manifest "$proof_manifest" \
  --rules-snapshot "$rules_snapshot" \
  --operation-id "aat-gate-c" 2>&1 || true)"

b_adm="$(printf '%s\n' "$b_out" | rg -m1 '^ADMISSIBLE=' | cut -d= -f2- || true)"
b_stop="$(printf '%s\n' "$b_out" | rg -m1 '^STOP_REQUIRED=' | cut -d= -f2- || true)"
b_reason="$(printf '%s\n' "$b_out" | rg -m1 '^REASON_CODE=' | cut -d= -f2- || true)"
b_action_seq="$(printf '%s\n' "$b_out" | rg -m1 '^ACTION_APPEND_SEQ=' | cut -d= -f2- || true)"
b_decision_seq="$(printf '%s\n' "$b_out" | rg -m1 '^DECISION_APPEND_SEQ=' | cut -d= -f2- || true)"

ledger_appended="NO"
if [[ -n "$b_action_seq" && -n "$b_decision_seq" ]]; then
  ledger_appended="YES"
fi

if [[ "$b_stop" == "YES" ]]; then
  echo "STATUS=HARD_STOP"
  echo "REASON_CODE=${b_reason:-AAT_GATE_C_GATE_B_HARD_STOP}"
  echo "LEDGER_APPENDED=$ledger_appended"
  exit 20
fi

if [[ "$b_adm" == "YES" ]]; then
  echo "STATUS=PASS"
  echo "REASON_CODE=NONE"
  echo "LEDGER_APPENDED=$ledger_appended"
  exit 0
fi

echo "STATUS=NON_ADMISSIBLE"
echo "REASON_CODE=${b_reason:-AAT_GATE_C_NON_ADMISSIBLE}"
echo "LEDGER_APPENDED=$ledger_appended"
exit 10
