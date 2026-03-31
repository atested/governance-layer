#!/usr/bin/env bash
# List next READY tasks from WORK_QUEUE.md "Next" section
# Output: one TASK_ID per line, in order

set -e

WORK_QUEUE="docs/dev/WORK_QUEUE.md"

if [ ! -f "$WORK_QUEUE" ]; then
  echo "ERROR: $WORK_QUEUE not found" >&2
  exit 1
fi

# Parse Next section
IN_NEXT=false
while IFS= read -r line; do
  # Detect "Next" section header
  if [[ "$line" =~ ^##[[:space:]]*Next ]]; then
    IN_NEXT=true
    continue
  fi
  
  # Exit Next section on next ## header
  if [ "$IN_NEXT" = true ] && [[ "$line" =~ ^## ]]; then
    break
  fi
  
  # Extract TASK_ID from lines in Next section
  if [ "$IN_NEXT" = true ] && [[ "$line" =~ TASK_[0-9]+ ]]; then
    TASK_ID="${BASH_REMATCH[0]}"
    echo "$TASK_ID"
  fi
done < "$WORK_QUEUE"
