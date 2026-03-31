#!/usr/bin/env bash
set -euo pipefail
src="${1:-/dev/stdin}"
content="$(cat "$src")"
printf '%s\n' "$content" | rg '^(ADMISSIBLE|STOP_REQUIRED|REASON_CODE|ACTION_APPEND_SEQ|DECISION_APPEND_SEQ)=' | LC_ALL=C sort
