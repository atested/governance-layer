#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bundle_dir=""
strict="0"
outcome_file=""
preflight_inputs="0"
preflight_inputs_parity="0"

usage() {
  cat <<'EOF'
usage: scripts/run_validate_proof_bundle_with_aat_shim.sh --bundle-dir <dir> [--strict 0|1] [--outcome-file <path>] [--preflight-inputs] [--preflight-inputs-parity]
EOF
}

derive_required_tokens() {
  python3 - <<'PY' "$ROOT/scripts/aat_stage_into_proof_bundle.py"
import ast
import sys
from pathlib import Path

path = Path(sys.argv[1])
tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
for node in tree.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "REQUIRED_FILES":
                value = ast.literal_eval(node.value)
                if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                    raise SystemExit(2)
                for item in sorted(value):
                    print(item)
                raise SystemExit(0)
raise SystemExit(2)
PY
}

emit_preflight() {
  local ok="$1"
  local layout="$2"
  local missing="$3"
  printf 'AAT_SHIM_INPUTS_PREFLIGHT ok=%s layout=%s missing=%s\n' "$ok" "$layout" "$missing"
}

emit_parity() {
  local ok="$1"
  local reason="$2"
  local detail="$3"
  printf 'AAT_SHIM_INPUTS_PARITY ok=%s reason=%s detail=%s\n' "$ok" "$reason" "$detail"
}

extract_stop_code_from_output() {
  local text="$1"
  local hard_stop_line reason=""
  hard_stop_line="$(printf '%s\n' "$text" | rg -m1 '^AAT_SHIM_RESULT=HARD_STOP' || true)"
  if [[ -n "$hard_stop_line" ]]; then
    reason="$(printf '%s\n' "$hard_stop_line" | rg -o -m1 'REASON_CODE=[^[:space:]]+' | cut -d= -f2- || true)"
    if [[ -n "$reason" ]]; then
      printf '%s\n' "$reason"
      return 0
    fi
  fi

  reason="$(printf '%s\n' "$text" | rg -m1 '^AAT_SHIM_REASON=[^[:space:]]+' | cut -d= -f2- || true)"
  if [[ -n "$reason" ]]; then
    printf '%s\n' "$reason"
    return 0
  fi

  reason="$(printf '%s\n' "$text" | rg -m1 '^AAT_INPUTS_SUBREASON=[^[:space:]]+' | cut -d= -f2- || true)"
  if [[ -n "$reason" ]]; then
    printf '%s\n' "$reason"
    return 0
  fi

  reason="$(printf '%s\n' "$text" | rg -m1 '^REASON_CODE=[^[:space:]]+' | cut -d= -f2- || true)"
  if [[ -n "$reason" ]]; then
    printf '%s\n' "$reason"
    return 0
  fi

  printf 'UNKNOWN\n'
}

json_parse_ok() {
  python3 - <<'PY' "$1" >/dev/null 2>&1
import json,sys
json.load(open(sys.argv[1], encoding="utf-8"))
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle-dir) bundle_dir="$2"; shift 2 ;;
    --strict) strict="$2"; shift 2 ;;
    --outcome-file) outcome_file="$2"; shift 2 ;;
    --preflight-inputs) preflight_inputs="1"; shift ;;
    --preflight-inputs-parity) preflight_inputs_parity="1"; shift ;;
    --_extract-stop-code) extract_stop_code_from_output "$2"; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

[[ -n "$bundle_dir" ]] || { echo "ERROR: --bundle-dir required" >&2; exit 2; }
[[ -d "$bundle_dir" ]] || { echo "ERROR: bundle dir not found: $bundle_dir" >&2; exit 2; }
[[ "$strict" == "0" || "$strict" == "1" ]] || { echo "ERROR: --strict must be 0 or 1" >&2; exit 2; }

if [[ "$preflight_inputs_parity" == "1" ]]; then
  required_tokens=()
  while IFS= read -r token; do
    [[ -n "$token" ]] && required_tokens+=("$token")
  done < <(derive_required_tokens || true)
  if [[ "${#required_tokens[@]}" -eq 0 ]]; then
    emit_parity "no" "UNKNOWN" "UNKNOWN"
    exit 2
  fi

  legacy_has_any=0
  aat_has_any=0
  evidence_aat_has_any=0
  for token in "${required_tokens[@]}"; do
    [[ -f "$bundle_dir/$token" ]] && legacy_has_any=1
    [[ -f "$bundle_dir/aat/$token" ]] && aat_has_any=1
    [[ -f "$bundle_dir/evidence/aat/$token" ]] && evidence_aat_has_any=1
  done

  if [[ "$legacy_has_any" -eq 1 && "$aat_has_any" -eq 1 ]]; then
    emit_parity "no" "AMBIGUOUS" "LEGACY_AND_AAT_BOTH_PRESENT"
    exit 2
  fi
  if [[ "$evidence_aat_has_any" -eq 1 ]]; then
    emit_parity "no" "AMBIGUOUS" "MULTIPLE_AAT_DIRS"
    exit 2
  fi

  layout=""
  prefix=""
  if [[ "$aat_has_any" -eq 1 ]]; then
    layout="aat"
    prefix="$bundle_dir/aat"
  elif [[ "$legacy_has_any" -eq 1 ]]; then
    layout="legacy"
    prefix="$bundle_dir"
  else
    first_missing="$(printf '%s\n' "${required_tokens[@]}" | LC_ALL=C sort | head -n1)"
    emit_parity "no" "MISSING" "$first_missing"
    exit 1
  fi

  missing_tokens=()
  for token in "${required_tokens[@]}"; do
    [[ -f "$prefix/$token" ]] || missing_tokens+=("$token")
  done
  if [[ "${#missing_tokens[@]}" -gt 0 ]]; then
    first_missing="$(printf '%s\n' "${missing_tokens[@]}" | LC_ALL=C sort | head -n1)"
    emit_parity "no" "MISSING" "$first_missing"
    exit 1
  fi

  for token in "${required_tokens[@]}"; do
    if ! json_parse_ok "$prefix/$token"; then
      emit_parity "no" "INVALID" "$token"
      exit 1
    fi
  done

  emit_parity "yes" "OK" "NONE"
  exit 0
fi

if [[ "$preflight_inputs" == "1" ]]; then
  required_tokens=()
  while IFS= read -r token; do
    [[ -n "$token" ]] && required_tokens+=("$token")
  done < <(derive_required_tokens || true)
  if [[ "${#required_tokens[@]}" -eq 0 ]]; then
    emit_preflight "no" "ambiguous" "NONE"
    exit 2
  fi

  missing_legacy=()
  missing_aat=()
  missing_evidence_aat=()
  local_legacy_present=0
  local_aat_present=0
  local_evidence_aat_present=0

  for token in "${required_tokens[@]}"; do
    if [[ -f "$bundle_dir/$token" ]]; then
      local_legacy_present=1
    else
      missing_legacy+=("$token")
    fi

    if [[ -f "$bundle_dir/aat/$token" ]]; then
      local_aat_present=1
    else
      missing_aat+=("$token")
    fi

    if [[ -f "$bundle_dir/evidence/aat/$token" ]]; then
      local_evidence_aat_present=1
    else
      missing_evidence_aat+=("$token")
    fi
  done

  legacy_complete=0
  aat_complete=0
  evidence_aat_complete=0
  [[ "${#missing_legacy[@]}" -eq 0 ]] && legacy_complete=1
  [[ "${#missing_aat[@]}" -eq 0 ]] && aat_complete=1
  [[ "${#missing_evidence_aat[@]}" -eq 0 ]] && evidence_aat_complete=1

  if [[ "$aat_complete" -eq 1 && "$legacy_complete" -eq 0 && "$evidence_aat_complete" -eq 0 ]]; then
    emit_preflight "yes" "aat" "NONE"
    exit 0
  fi
  if [[ "$legacy_complete" -eq 1 && "$aat_complete" -eq 0 && "$evidence_aat_complete" -eq 0 ]]; then
    emit_preflight "yes" "legacy" "NONE"
    exit 0
  fi
  if [[ "$evidence_aat_complete" -eq 1 && "$aat_complete" -eq 0 && "$legacy_complete" -eq 0 ]]; then
    emit_preflight "no" "ambiguous" "NONE"
    exit 2
  fi

  # Any multi-layout presence is ambiguous, even if one is complete.
  layouts_present=0
  [[ "$local_legacy_present" -eq 1 || "$legacy_complete" -eq 1 ]] && layouts_present=$((layouts_present + 1))
  [[ "$local_aat_present" -eq 1 || "$aat_complete" -eq 1 ]] && layouts_present=$((layouts_present + 1))
  [[ "$local_evidence_aat_present" -eq 1 || "$evidence_aat_complete" -eq 1 ]] && layouts_present=$((layouts_present + 1))
  if [[ "$layouts_present" -gt 1 ]]; then
    if [[ "${#missing_legacy[@]}" -eq 0 && "${#missing_aat[@]}" -eq 0 && "${#missing_evidence_aat[@]}" -eq 0 ]]; then
      emit_preflight "no" "ambiguous" "NONE"
    else
      missing_csv="$(printf '%s\n' "${missing_legacy[@]}" "${missing_aat[@]}" "${missing_evidence_aat[@]}" | awk 'NF' | LC_ALL=C sort -u | paste -sd, -)"
      emit_preflight "no" "ambiguous" "$missing_csv"
    fi
    exit 2
  fi

  # Single-layout partial detection.
  if [[ "$local_aat_present" -eq 1 ]]; then
    missing_csv="$(printf '%s\n' "${missing_aat[@]}" | awk 'NF' | LC_ALL=C sort -u | paste -sd, -)"
    emit_preflight "no" "aat" "$missing_csv"
    exit 1
  fi
  if [[ "$local_legacy_present" -eq 1 ]]; then
    missing_csv="$(printf '%s\n' "${missing_legacy[@]}" | awk 'NF' | LC_ALL=C sort -u | paste -sd, -)"
    emit_preflight "no" "legacy" "$missing_csv"
    exit 1
  fi
  if [[ "$local_evidence_aat_present" -eq 1 ]]; then
    missing_csv="$(printf '%s\n' "${missing_evidence_aat[@]}" | awk 'NF' | LC_ALL=C sort -u | paste -sd, -)"
    emit_preflight "no" "ambiguous" "$missing_csv"
    exit 2
  fi

  missing_csv="$(printf '%s\n' "${required_tokens[@]}" | LC_ALL=C sort | paste -sd, -)"
  emit_preflight "no" "none" "$missing_csv"
  exit 1
fi

set +e
out="$(AAT_SHIM_ENABLE=1 AAT_SHIM_STRICT="$strict" bash system/scripts/validate-proof-bundle.sh "$bundle_dir" 2>&1)"
rc=$?
set -e

shim_status_raw="$(printf '%s\n' "$out" | rg -m1 '^AAT_SHIM_RESULT=' | sed -E 's/^AAT_SHIM_RESULT=([^[:space:]]+).*$/\1/' || true)"

shim_status="UNKNOWN"
case "$shim_status_raw" in
  PASS) shim_status="ADMISSIBLE" ;;
  NON_ADMISSIBLE) shim_status="NON_ADMISSIBLE" ;;
  HARD_STOP) shim_status="STOP" ;;
  "")
    if [[ "$rc" -eq 0 ]]; then
      shim_status="ADMISSIBLE"
    fi
    ;;
esac

stop_stage="UNKNOWN"
stop_code="NONE"
if [[ "$shim_status" == "STOP" ]]; then
  stop_code="$(extract_stop_code_from_output "$out")"
  if [[ "$shim_status_raw" == "HARD_STOP" ]]; then
    stop_stage="SHIM"
  else
    stop_stage="PRE_SHIM"
  fi
fi

outcome_line="AAT_SHIM_OUTCOME strict=$strict rc=$rc shim_status=$shim_status stop_stage=$stop_stage stop_code=$stop_code"
printf '%s\n' "$outcome_line"

if [[ -n "$outcome_file" ]]; then
  mkdir -p "$(dirname "$outcome_file")"
  {
    printf 'strict=%s\n' "$strict"
    printf 'rc=%s\n' "$rc"
    printf 'shim_status=%s\n' "$shim_status"
    printf 'stop_stage=%s\n' "$stop_stage"
    printf 'stop_code=%s\n' "$stop_code"
  } > "$outcome_file"
fi

exit "$rc"
