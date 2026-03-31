#!/usr/bin/env bash
set -euo pipefail

proof_bundle_dir=""
ledger_path=""
surface_catalog="system/schemas/foundation_v0_surface_catalog.json"
typed_ref_catalog="system/schemas/typed_ref_catalog.json"

usage() {
  cat <<'EOF'
usage: system/scripts/foundation-v0-admissibility-gate.sh --proof-bundle-dir <path> [--ledger-path <path>] [--surface-catalog <path>] [--typed-ref-catalog <path>]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --proof-bundle-dir) proof_bundle_dir="$2"; shift 2 ;;
    --ledger-path) ledger_path="$2"; shift 2 ;;
    --surface-catalog) surface_catalog="$2"; shift 2 ;;
    --typed-ref-catalog) typed_ref_catalog="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ADMISSIBLE=NO"; echo "STOP_REQUIRED=YES"; echo "REASON_CODE=FV0_BAD_ARGS"; exit 2 ;;
  esac
done

emit() {
  local admissible="$1" stop_required="$2" reason="$3" rc="$4"
  echo "ADMISSIBLE=${admissible}"
  echo "STOP_REQUIRED=${stop_required}"
  echo "REASON_CODE=${reason}"
  exit "$rc"
}

[[ -n "$proof_bundle_dir" ]] || emit NO YES FV0_MISSING_PROOF_BUNDLE_DIR 2
[[ -d "$proof_bundle_dir" ]] || emit NO YES FV0_PROOF_BUNDLE_DIR_NOT_FOUND 2
[[ -f "$surface_catalog" ]] || emit NO YES FV0_SURFACE_CATALOG_MISSING 2
[[ -f "$typed_ref_catalog" ]] || emit NO YES FV0_TYPED_REF_CATALOG_MISSING 2

if [[ -z "$ledger_path" ]]; then
  if [[ -f "$proof_bundle_dir/ledger.jsonl" ]]; then
    ledger_path="$proof_bundle_dir/ledger.jsonl"
  elif [[ -f "$proof_bundle_dir/process_ledger.jsonl" ]]; then
    ledger_path="$proof_bundle_dir/process_ledger.jsonl"
  else
    emit NO YES FV0_LEDGER_NOT_FOUND 2
  fi
fi
[[ -f "$ledger_path" ]] || emit NO YES FV0_LEDGER_NOT_FOUND 2

# 1) proof bundle verifier invocation (hot file script called read-only)
if ! system/scripts/validate-proof-bundle.sh "$proof_bundle_dir" >/dev/null 2>&1; then
  emit NO YES FV0_PROOF_BUNDLE_INVALID 2
fi

# 2 + 3) foundation ledger verify + coverage subset enforcement via verifier
report_file="$(mktemp)"
verify_out_file="$(mktemp)"
trap 'rm -f "$report_file" "$verify_out_file"' EXIT

set +e
python3 scripts/foundation_v0_process_ledger.py verify \
  --ledger "$ledger_path" \
  --artifact-dir "$proof_bundle_dir" \
  --report-out "$report_file" \
  >"$verify_out_file" 2>&1
verify_rc=$?
set -e

if [[ "$verify_rc" -ne 0 ]]; then
  reason="FV0_LEDGER_VERIFY_ERROR"
  for code in CHAIN_BREAK ENTRY_HASH_MISMATCH APPEND_SEQ_BREAK SCHEMA_INVALID SERIALIZATION_FAILURE; do
    if rg -n "^${code}$" "$verify_out_file" >/dev/null; then
      reason="$code"
      break
    fi
  done
  emit NO YES "$reason" 2
fi

if [[ ! -s "$report_file" ]]; then
  emit NO YES FV0_LEDGER_REPORT_MISSING 2
fi

status="$(python3 - "$report_file" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]))
print(r.get('overall_status','UNKNOWN'))
PY
)"

if [[ "$status" == "ADMISSIBLE" ]]; then
  emit YES NO RC_OK 0
fi

if [[ "$status" == "NON_ADMISSIBLE" ]]; then
  reason="$(python3 - "$report_file" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]))
codes=[]
for e in r.get('entries',[]):
  codes.extend(e.get('failure_codes',[]))
codes=sorted(set(codes))
print(codes[0] if codes else 'FV0_NON_ADMISSIBLE')
PY
)"
  emit NO NO "$reason" 1
fi

emit NO YES FV0_LEDGER_REPORT_INVALID 2
