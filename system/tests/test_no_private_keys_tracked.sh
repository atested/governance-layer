#!/usr/bin/env bash
set -euo pipefail

# Ensure no private key PEM blocks are tracked in git outside the
# designated test fixture directory.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ALLOWED_DIR="system/tests/fixtures/keys/"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

set +e
git ls-files -z | xargs -0 rg -l -- '-----BEGIN PRIVATE KEY-----' | grep -v 'test_no_private_keys_tracked\.sh' > "$tmp"
rc=$?
set -e

if [[ "$rc" -eq 1 ]]; then
  # No matches — clean
  echo "CASE=NO_PRIVATE_KEYS_TRACKED PASS"
  exit 0
fi

if [[ "$rc" -ne 0 ]]; then
  echo "FAIL:SCAN_ERROR"
  exit 1
fi

# Filter out allowed directory
violations=""
while IFS= read -r f; do
  case "$f" in
    "$ALLOWED_DIR"*) ;;  # allowed
    *) violations="$violations$f"$'\n' ;;
  esac
done < "$tmp"

if [[ -n "$violations" ]]; then
  echo "FAIL: Private key PEM blocks found in tracked files outside $ALLOWED_DIR:"
  echo "$violations"
  echo "FAIL:PRIVATE_KEYS_TRACKED"
  exit 1
fi

echo "CASE=NO_PRIVATE_KEYS_TRACKED PASS"
exit 0
