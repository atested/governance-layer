#!/usr/bin/env bash
set -euo pipefail
src="${1:-/dev/stdin}"
content="$(cat "$src")"
printf '%s\n' "$content" | rg '^(STATUS|REASON_CODE|LEDGER_APPENDED)=' | LC_ALL=C sort
