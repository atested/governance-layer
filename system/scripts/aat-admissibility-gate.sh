#!/usr/bin/env bash
# AAT Admissibility Gate - Wrapper script for Action Admissibility Testing
#
# This wrapper integrates AAT validation into the release-gate system.
# It produces machine-readable output following the same pattern as
# foundation-v0-admissibility-gate.sh.

set -euo pipefail

action_bundle_dir=""
schema_dir="system/schemas"
repo_root="."
enforcement_mode="ENFORCING"
profile=""

usage() {
  cat <<'EOF'
usage: system/scripts/aat-admissibility-gate.sh --action-bundle-dir <path> [options]

Options:
  --action-bundle-dir <path>  Directory containing AAT kernel objects (required)
  --schema-dir <path>         Schema directory (default: system/schemas)
  --repo-root <path>          Repository root (default: current directory)
  --enforcement-mode <mode>   ENFORCING or REPORT_ONLY (default: ENFORCING)
  --profile <name>            Explicit AAT profile override (default: method binding)
  -h, --help                  Show this help message

Output format:
  ADMISSIBLE=YES|NO
  STOP_REQUIRED=YES|NO
  REASON_CODE=<first_reason_code_or_NONE>
  ENFORCEMENT_MODE=ENFORCING|REPORT_ONLY

Exit codes:
  0 - PASS (admissible)
  1 - FAIL_NON_ADMISSIBLE (not admissible, override possible)
  2 - FAIL_HARD_STOP (hard stop, no override)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --action-bundle-dir) action_bundle_dir="$2"; shift 2 ;;
    --schema-dir) schema_dir="$2"; shift 2 ;;
    --repo-root) repo_root="$2"; shift 2 ;;
    --enforcement-mode) enforcement_mode="$2"; shift 2 ;;
    --profile) profile="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "ADMISSIBLE=NO"
      echo "STOP_REQUIRED=YES"
      echo "REASON_CODE=AAT_BAD_ARGS"
      echo "ENFORCEMENT_MODE=ENFORCING"
      exit 2
      ;;
  esac
done

emit() {
  local admissible="$1" stop_required="$2" reason="$3" rc="$4"
  echo "ADMISSIBLE=${admissible}"
  echo "STOP_REQUIRED=${stop_required}"
  echo "REASON_CODE=${reason}"
  echo "ENFORCEMENT_MODE=${enforcement_mode}"
  exit "$rc"
}

# Validate arguments
[[ -n "$action_bundle_dir" ]] || emit NO YES AAT_MISSING_BUNDLE_DIR 2
[[ -d "$action_bundle_dir" ]] || emit NO YES AAT_BUNDLE_DIR_NOT_FOUND 2
[[ -d "$schema_dir" ]] || emit NO YES AAT_SCHEMA_DIR_NOT_FOUND 2

# Validate enforcement mode
if [[ "$enforcement_mode" != "ENFORCING" && "$enforcement_mode" != "REPORT_ONLY" ]]; then
  emit NO YES AAT_INVALID_ENFORCEMENT_MODE 2
fi

# Run AAT main orchestrator
adr_file="$(mktemp)"
trap 'rm -f "$adr_file"' EXIT

set +e
if [[ -n "$profile" ]]; then
  python3 "$repo_root/scripts/aat_main.py" \
    --bundle-dir "$action_bundle_dir" \
    --schema-dir "$schema_dir" \
    --repo-root "$repo_root" \
    --enforcement-mode "$enforcement_mode" \
    --profile "$profile" \
    --output "$adr_file" \
    2>/dev/null
else
  python3 "$repo_root/scripts/aat_main.py" \
    --bundle-dir "$action_bundle_dir" \
    --schema-dir "$schema_dir" \
    --repo-root "$repo_root" \
    --enforcement-mode "$enforcement_mode" \
    --output "$adr_file" \
    2>/dev/null
fi
aat_rc=$?
set -e

# Check if ADR was created
if [[ ! -f "$adr_file" || ! -s "$adr_file" ]]; then
  emit NO YES AAT_VALIDATION_FAILED 2
fi

# Parse ADR decision
decision=$(python3 - "$adr_file" <<'PY'
import json, sys
try:
  adr = json.load(open(sys.argv[1]))
  print(adr.get('decision', 'UNKNOWN'))
except:
  print('UNKNOWN')
PY
)

# Get first reason code if any
reason_code=$(python3 - "$adr_file" <<'PY'
import json, sys
try:
  adr = json.load(open(sys.argv[1]))
  codes = adr.get('reason_codes', [])
  print(codes[0] if codes else 'NONE')
except:
  print('NONE')
PY
)

# Map decision to output
case "$decision" in
  PASS)
    emit YES NO NONE 0
    ;;
  FAIL_NON_ADMISSIBLE)
    emit NO NO "$reason_code" 1
    ;;
  FAIL_HARD_STOP)
    emit NO YES "$reason_code" 2
    ;;
  *)
    emit NO YES AAT_UNKNOWN_DECISION 2
    ;;
esac
