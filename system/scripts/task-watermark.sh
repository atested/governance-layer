#!/usr/bin/env bash
set -euo pipefail

# task-watermark.sh
# Deterministic ready task pool watermark check.
# Reports READY_COUNT, READY_MIN, LOW, SEED_PRESENT.
# Exit 0 always (reporting only, not a gate).

# Configurable minimum ready task threshold
READY_MIN="${READY_MIN:-8}"

# Repo root check
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ "$ROOT" != "/Volumes/SSD/archive/gov/governance-layer" ]; then
  echo "ERROR: Must run from governance-layer repo root" >&2
  exit 1
fi

# Count READY task files
READY_DIR="docs/dev/tasks/ready"
READY_COUNT=0

if [ -d "$READY_DIR" ]; then
  # Count files matching TASK_*.md pattern
  READY_COUNT=$(find "$READY_DIR" -maxdepth 1 -type f -name "TASK_*.md" | wc -l | tr -d ' ')
fi

# Check if low
LOW=0
if [ "$READY_COUNT" -lt "$READY_MIN" ]; then
  LOW=1
fi

# Check if seed file present and compute hash
SEED_FILE="docs/dev/task-seeds/SEED.md"
SEED_PRESENT=0
SEED_HASH="none"
if [ -f "$SEED_FILE" ]; then
  SEED_PRESENT=1
  SEED_HASH=$(shasum -a 256 "$SEED_FILE" | awk '{print $1}')
fi

# Extract last seed file and hash from previous scaffold run
SCAFFOLD_LAST="ops/TASK_SCAFFOLD_LAST.json"
LAST_SEED_FILE="none"
LAST_SEED_HASH="none"
if [ -f "$SCAFFOLD_LAST" ]; then
  # Extract seed_file field
  LAST_SEED_FILE=$(grep -oE '"seed_file"\s*:\s*"[^"]+"' "$SCAFFOLD_LAST" | sed -E 's/.*"([^"]+)".*/\1/' || echo "")
  if [ -z "$LAST_SEED_FILE" ]; then
    LAST_SEED_FILE="none"
  fi

  # Extract seed_hash field
  LAST_SEED_HASH=$(grep -oE '"seed_hash"\s*:\s*"[^"]+"' "$SCAFFOLD_LAST" | sed -E 's/.*"([^"]+)".*/\1/' || echo "none")
  if [ -z "$LAST_SEED_HASH" ]; then
    LAST_SEED_HASH="none"
  fi

  # Only use LAST_SEED_HASH if last scaffold used the same seed file
  if [ "$LAST_SEED_FILE" != "$SEED_FILE" ]; then
    LAST_SEED_HASH="none"
  fi
fi

# Determine if prompt needed: LOW=1 AND SEED_PRESENT=1 AND seed changed
PROMPT=0
if [ "$LOW" -eq 1 ] && [ "$SEED_PRESENT" -eq 1 ] && [ "$LAST_SEED_HASH" != "$SEED_HASH" ]; then
  PROMPT=1
fi

# Output machine-readable status
echo "READY_COUNT=$READY_COUNT READY_MIN=$READY_MIN LOW=$LOW SEED_PRESENT=$SEED_PRESENT SEED_HASH=$SEED_HASH LAST_SEED_FILE=$LAST_SEED_FILE LAST_SEED_HASH=$LAST_SEED_HASH PROMPT=$PROMPT"

# Human summary
if [ "$LOW" -eq 1 ]; then
  echo "Ready task pool is low: $READY_COUNT tasks < $READY_MIN threshold" >&2
  if [ "$SEED_PRESENT" -eq 1 ]; then
    echo "Seed file present: $SEED_FILE" >&2
    if [ "$LAST_SEED_FILE" != "$SEED_FILE" ] && [ "$LAST_SEED_FILE" != "none" ]; then
      echo "Last scaffold used different seed file ($LAST_SEED_FILE), treating as first run" >&2
    fi
    if [ "$PROMPT" -eq 1 ]; then
      echo "Seed file has changed since last scaffold (prompt recommended)" >&2
    else
      echo "Seed file unchanged since last scaffold (no prompt)" >&2
    fi
  else
    echo "No seed file found at $SEED_FILE" >&2
  fi
else
  echo "Ready task pool is sufficient: $READY_COUNT tasks >= $READY_MIN threshold" >&2
fi

exit 0
