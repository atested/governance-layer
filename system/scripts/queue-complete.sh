#!/usr/bin/env bash
# Mark a task as DONE in WORK_QUEUE.md
# Usage: queue-complete.sh TASK_ID BRANCH COMMIT

set -e

TASK_ID="${1:-}"
BRANCH="${2:-}"
COMMIT="${3:-}"

if [ -z "$TASK_ID" ] || [ -z "$BRANCH" ] || [ -z "$COMMIT" ]; then
  echo "ERROR: Missing arguments"
  echo "Usage: $0 TASK_ID BRANCH COMMIT"
  exit 1
fi

WORK_QUEUE="docs/dev/WORK_QUEUE.md"

if [ ! -f "$WORK_QUEUE" ]; then
  echo "ERROR: $WORK_QUEUE not found"
  exit 1
fi

# Create backup
cp "$WORK_QUEUE" "$WORK_QUEUE.bak"

# Mark task complete
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "# Completed: $TASK_ID ($BRANCH @ $COMMIT) at $TIMESTAMP" >> "$WORK_QUEUE"

echo "Completed: $TASK_ID on $BRANCH @ $COMMIT"
