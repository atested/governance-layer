#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TEMPLATE="docs/dev/STOP_PACKET_TEMPLATE__v1.txt"
[[ -f "$TEMPLATE" ]] || { echo "FAIL:TEMPLATE_MISSING"; exit 1; }

for key in STOP_REASON= CONTEXT= ACTION_REQUIRED= NEXT_STEP=; do
  rg -q "^${key}" "$TEMPLATE" || { echo "FAIL:MISSING_KEY:${key}"; exit 1; }
done

rg -q '^<<<<<<<|^=======$|^>>>>>>>' "$TEMPLATE" && { echo "FAIL:CONFLICT_MARKER_PRESENT"; exit 1; }
rg -q $'\t' "$TEMPLATE" && { echo "FAIL:TAB_PRESENT"; exit 1; }

echo "CASE=STOP_PACKET_TEMPLATE_GUARD PASS"
