#!/usr/bin/env bash
# Enforce task-level Allowed/Forbidden files scope
# Usage: enforce-task-scope.sh <ref> <task_file_path>
# Exit: 0 on PASS, non-zero on FAIL

set -e

REF="${1:-}"
TASK_FILE="${2:-}"

if [ -z "$REF" ] || [ -z "$TASK_FILE" ]; then
  echo "ERROR: Missing arguments"
  echo "Usage: $0 <ref> <task_file_path>"
  exit 1
fi

# Ensure we're in a git repo
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "ERROR: Not in a git repository"
  exit 1
fi

# Fetch task file contents from ref
TASK_CONTENT=$(git show "$REF:$TASK_FILE" 2>/dev/null || echo "")
if [ -z "$TASK_CONTENT" ]; then
  echo "ERROR: Cannot read task file from ref"
  echo "Ref: $REF"
  echo "Task file: $TASK_FILE"
  exit 1
fi

# Parse Allowed Files section
ALLOWED_FILES=()
IN_ALLOWED=false
while IFS= read -r line; do
  if [[ "$line" =~ ^##[[:space:]]*Files[[:space:]]+allowed[[:space:]]+to[[:space:]]+touch ]]; then
    IN_ALLOWED=true
    continue
  fi
  if [[ "$line" =~ ^## ]]; then
    IN_ALLOWED=false
  fi
  if [ "$IN_ALLOWED" = true ] && [[ "$line" =~ ^-[[:space:]]+(.+)$ ]]; then
    FILE="${BASH_REMATCH[1]}"
    # Strip any trailing comments or whitespace
    FILE=$(echo "$FILE" | sed 's/[[:space:]]*#.*//' | xargs)
    if [ -n "$FILE" ]; then
      ALLOWED_FILES+=("$FILE")
    fi
  fi
done <<< "$TASK_CONTENT"

# Parse Forbidden Files section
FORBIDDEN_FILES=()
IN_FORBIDDEN=false
while IFS= read -r line; do
  if [[ "$line" =~ ^##[[:space:]]*Files[[:space:]]+forbidden[[:space:]]+to[[:space:]]+touch ]]; then
    IN_FORBIDDEN=true
    continue
  fi
  if [[ "$line" =~ ^## ]]; then
    IN_FORBIDDEN=false
  fi
  if [ "$IN_FORBIDDEN" = true ] && [[ "$line" =~ ^-[[:space:]]+(.+)$ ]]; then
    FILE="${BASH_REMATCH[1]}"
    FILE=$(echo "$FILE" | sed 's/[[:space:]]*#.*//' | xargs)
    if [ -n "$FILE" ]; then
      FORBIDDEN_FILES+=("$FILE")
    fi
  fi
done <<< "$TASK_CONTENT"

# Fail if allowlist is empty
if [ ${#ALLOWED_FILES[@]} -eq 0 ]; then
  echo "FAIL: Task scope violation"
  echo "Ref: $REF"
  echo "Task file: $TASK_FILE"
  echo "ERROR: Allowed files list is empty"
  echo "Task file must define allowed files in '## Files allowed to touch' section"
  exit 1
fi

# Get changed files
CHANGED_FILES=$(git diff --name-only origin/main..."$REF" 2>/dev/null || echo "")
if [ -z "$CHANGED_FILES" ]; then
  echo "PASS: No files changed"
  echo "Ref: $REF"
  echo "Task file: $TASK_FILE"
  exit 0
fi

# Check each changed file
VIOLATIONS=()
FIRST_VIOLATION=""

while IFS= read -r changed_file; do
  [ -z "$changed_file" ] && continue
  
  # Hard fail on ASSIGNMENTS.md
  if [ "$changed_file" = "docs/dev/ASSIGNMENTS.md" ]; then
    echo "FAIL: Task scope violation"
    echo "Ref: $REF"
    echo "Task file: $TASK_FILE"
    echo "ERROR: docs/dev/ASSIGNMENTS.md must not be modified by task branches"
    echo "Changed files:"
    echo "$CHANGED_FILES" | sed 's/^/  /'
    echo "First violation: $changed_file"
    exit 1
  fi
  
  # Check forbidden list
  for forbidden in "${FORBIDDEN_FILES[@]}"; do
    if [ "$changed_file" = "$forbidden" ]; then
      VIOLATIONS+=("$changed_file (forbidden)")
      [ -z "$FIRST_VIOLATION" ] && FIRST_VIOLATION="$changed_file (forbidden)"
      continue 2
    fi
  done
  
  # Check allowed list
  ALLOWED=false
  for allowed in "${ALLOWED_FILES[@]}"; do
    if [ "$changed_file" = "$allowed" ]; then
      ALLOWED=true
      break
    fi
  done
  
  if [ "$ALLOWED" = false ]; then
    VIOLATIONS+=("$changed_file (not in allowed list)")
    [ -z "$FIRST_VIOLATION" ] && FIRST_VIOLATION="$changed_file (not in allowed list)"
  fi
done <<< "$CHANGED_FILES"

# Report results
if [ ${#VIOLATIONS[@]} -eq 0 ]; then
  echo "PASS: Task scope enforced"
  echo "Ref: $REF"
  echo "Task file: $TASK_FILE"
  echo "Changed files: $(echo "$CHANGED_FILES" | wc -l | xargs)"
  exit 0
else
  echo "FAIL: Task scope violation"
  echo "Ref: $REF"
  echo "Task file: $TASK_FILE"
  echo "Changed files:"
  echo "$CHANGED_FILES" | sed 's/^/  /'
  echo ""
  echo "Violations (${#VIOLATIONS[@]}):"
  for violation in "${VIOLATIONS[@]}"; do
    echo "  - $violation"
  done
  echo ""
  echo "First violation: $FIRST_VIOLATION"
  echo ""
  echo "Allowed files (${#ALLOWED_FILES[@]}):"
  for allowed in "${ALLOWED_FILES[@]}"; do
    echo "  - $allowed"
  done
  exit 1
fi
