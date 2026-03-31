#!/usr/bin/env bash
set -euo pipefail

input="${1:-}"
if [[ -n "$input" ]]; then
  src="$input"
else
  src="/dev/stdin"
fi

ad="$(rg -m1 '^ADMISSIBLE=' "$src" | cut -d= -f2- || true)"
st="$(rg -m1 '^STOP_REQUIRED=' "$src" | cut -d= -f2- || true)"
rc="$(rg -m1 '^REASON_CODE=' "$src" | cut -d= -f2- || true)"

[[ -n "$ad" ]] || ad="NO"
[[ -n "$st" ]] || st="YES"
[[ -n "$rc" ]] || rc="FV0_NORMALIZER_MISSING_REASON"

echo "ADMISSIBLE=$ad"
echo "STOP_REQUIRED=$st"
echo "REASON_CODE=$rc"
