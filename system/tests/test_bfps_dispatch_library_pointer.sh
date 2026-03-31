#!/usr/bin/env bash
set -euo pipefail

BFPS="docs/dev/BRIEFING_FORMAT__BFPS_v12.md"
CANON="docs/dev/DISPATCH_LIBRARY__CECIL_CODEX__CANON.md"

[[ -f "$BFPS" ]] || { echo "FAIL:missing_bfps"; exit 1; }
[[ -f "$CANON" ]] || { echo "FAIL:missing_canon_dispatch"; exit 1; }

rg -n 'DISPATCH_LIBRARY__CECIL_CODEX__CANON\.md' "$BFPS" >/dev/null || {
  echo "FAIL:bfps_missing_canon_pointer"
  exit 1
}

if rg -n 'DISPATCH_LIBRARY__CECIL_CODEX__v[0-9]+\.md' "$BFPS" >/dev/null; then
  echo "FAIL:bfps_references_versioned_dispatch_library"
  exit 1
fi

echo "CASE=BFPS_DISPATCH_LIBRARY_POINTER PASS"
