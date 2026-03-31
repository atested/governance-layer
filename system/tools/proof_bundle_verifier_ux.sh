#!/bin/bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: proof_bundle_verifier_ux.sh <exit_code> <failed_path> <hint>" >&2
  exit 2
fi

exit_code="$1"
failed_path="$2"
hint="$3"

if ! [[ "$exit_code" =~ ^[0-9]+$ ]]; then
  echo "invalid exit_code: $exit_code" >&2
  exit 2
fi

if [[ "$exit_code" -eq 0 ]]; then
  echo "VERIFIER_OK"
  echo "EXIT_CODE=0"
  exit 0
fi

echo "VERIFIER_FAIL"
echo "EXIT_CODE=$exit_code"
echo "FAILED_PATH=$failed_path"
echo "HINT=$hint"
exit "$exit_code"
