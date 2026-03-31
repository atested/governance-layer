#!/usr/bin/env bash
# Claim a task for an actor in WORK_QUEUE.md
# Usage: queue-claim.sh TASK_ID ACTOR

set -e

TASK_ID="${1:-}"
ACTOR="${2:-}"

if [ -z "$TASK_ID" ] || [ -z "$ACTOR" ]; then
  echo "ERROR: Missing arguments"
  echo "Usage: $0 TASK_ID ACTOR"
  exit 1
fi

WORK_QUEUE="docs/dev/WORK_QUEUE.md"

if [ ! -f "$WORK_QUEUE" ]; then
  echo "ERROR: $WORK_QUEUE not found"
  exit 1
fi

# Create backup
cp "$WORK_QUEUE" "$WORK_QUEUE.bak"

# Update task status to IN_PROGRESS
# Look for the task line and append/update status
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Simple approach: add a note that task is claimed
# This is a simplified implementation - in production you'd want more robust state tracking
echo "# Claimed: $TASK_ID by $ACTOR at $TIMESTAMP" >> "$WORK_QUEUE"

echo "Claimed: $TASK_ID for $ACTOR"
