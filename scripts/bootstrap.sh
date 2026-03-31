#!/usr/bin/env bash
set -euo pipefail

# Minimal bootstrap helper: prints a checklist and ensures basic folders exist.
ROOT="${1:-.}"

mkdir -p "$ROOT/docs" "$ROOT/ops" "$ROOT/scripts" "$ROOT/LOGS"

echo "Bootstrap complete at: $ROOT"
echo
echo "Checklist:"
echo "1) Edit ops/ACTIVE-TASK.md for the next deliverable"
echo "2) Commit changes to docs/ and ops/"
echo "3) Add LOGS/ artifacts when tests run"
