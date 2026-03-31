#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

BFPS="docs/dev/BRIEFING_FORMAT__BFPS_v12.md"
DISPATCH="docs/dev/DISPATCH_LIBRARY__CECIL_CODEX__v10.md"
OPS="docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md"

for f in "$BFPS" "$DISPATCH" "$OPS"; do
  [[ -f "$f" ]] || { echo "FAIL:MISSING_FILE:$f"; exit 1; }
done

rg -q '^### 1\.9 Next chat creation protocol$|^#+ .*Next chat creation protocol' "$BFPS" || {
  echo "FAIL:BFPS_NEXT_CHAT_CREATION_PROTOCOL_HEADING_MISSING"
  exit 1
}

rg -q '(^|[^0-9])9\.1([^0-9]|$)' "$OPS" || {
  echo "FAIL:OPS_PROCESS_SECTION_9_1_MISSING"
  exit 1
}

# Best-effort warning only to avoid breaking existing content unexpectedly.
warn_paths="$(rg -n '/Users/|/Volumes/SSD/' "$BFPS" "$DISPATCH" "$OPS" || true)"
if [[ -n "$warn_paths" ]]; then
  echo "WARN:ABSOLUTE_PATHS_PRESENT"
else
  echo "WARN:ABSOLUTE_PATHS_PRESENT=NO"
fi

echo "CASE=DOC_POINTER_LINT PASS"
