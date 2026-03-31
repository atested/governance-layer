#!/usr/bin/env bash
set -euo pipefail

# Writes a timestamped report stub to LOGS/.
ROOT="${1:-.}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$ROOT/LOGS/report-$TS.md"

cat > "$OUT" <<'EOF'
# Test/Run Report

## What ran
- 

## Results
- Pass:
- Fail:

## Evidence
- Decision record(s):
- Log chain hash:
- Verifier output:

## Notes
-
EOF

echo "Wrote: $OUT"
