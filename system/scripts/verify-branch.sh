#!/usr/bin/env bash
# Verify a Codex branch meets evidence and policy requirements
# Usage: verify-branch.sh <ref>
# Exit: 0 on PASS, non-zero on FAIL

set -e

export GIT_PAGER=cat
export PAGER=cat
git config --global core.pager cat >/dev/null 2>&1 || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENFORCE_SCOPE_SCRIPT="$SCRIPT_DIR/enforce-task-scope.sh"

REF="${1:-}"

if [ -z "$REF" ]; then
  echo "ERROR: No ref provided"
  echo "Usage: $0 <ref>"
  exit 1
fi

# Ensure we're in a git repo
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "ERROR: Not in a git repository"
  exit 1
fi

# Ensure enforce-task-scope.sh exists
if [ ! -x "$ENFORCE_SCOPE_SCRIPT" ]; then
  echo "ERROR: enforce-task-scope.sh not found or not executable"
  exit 1
fi

# Fetch origin
echo "Fetching origin..."
git fetch origin --prune --quiet

# Resolve TASK_ID from ref name
if [[ "$REF" =~ TASK_[0-9]+ ]]; then
  TASK_ID="${BASH_REMATCH[0]}"
else
  echo "FAIL: Branch naming convention violated"
  echo "Ref: $REF"
  echo "Expected: codex/TASK_XXX format"
  exit 1
fi

# Determine merge base
BASE="origin/main"

# Get changed files
CHANGED_FILES=$(git --no-pager diff --name-only "$BASE...$REF" 2>/dev/null || echo "")
CHANGED_COUNT=$(echo "$CHANGED_FILES" | grep -c . || echo 0)

# Check for ASSIGNMENTS.md modification (should never happen, CI blocks this)
if echo "$CHANGED_FILES" | grep -q "^docs/dev/ASSIGNMENTS.md$"; then
  echo "FAIL: ASSIGNMENTS.md modified (policy violation)"
  echo "Ref: $REF"
  echo "TASK_ID: $TASK_ID"
  echo "Codex branches must not modify ASSIGNMENTS.md"
  exit 1
fi

# Find task file on the ref
echo "Locating task file for $TASK_ID..."
TASK_FILES=$(git ls-tree -r --name-only "$REF" docs/dev/tasks | grep "${TASK_ID}__" || echo "")
TASK_FILE_COUNT=$(echo "$TASK_FILES" | grep -c . || echo 0)

if [ "$TASK_FILE_COUNT" -eq 0 ]; then
  echo "FAIL: No task file found"
  echo "Ref: $REF"
  echo "TASK_ID: $TASK_ID"
  echo "Expected: docs/dev/tasks/**/${TASK_ID}__*.md"
  exit 1
elif [ "$TASK_FILE_COUNT" -gt 1 ]; then
  echo "FAIL: Multiple task files found"
  echo "Ref: $REF"
  echo "TASK_ID: $TASK_ID"
  echo "Found:"
  echo "$TASK_FILES" | sed 's/^/  /'
  echo "Expected: Exactly one task file"
  exit 1
fi

TASK_FILE="$TASK_FILES"
echo "Task file: $TASK_FILE"

# Enforce task scope (allowed/forbidden files)
echo "Enforcing task scope..."
if ! "$ENFORCE_SCOPE_SCRIPT" "$REF" "$TASK_FILE"; then
  echo "========================================="
  echo "FAIL: Task scope enforcement failed"
  echo "========================================="
  exit 1
fi

# Check for evidence bundle
EVIDENCE_DIR="docs/dev/evidence/$TASK_ID"
REQUIRED_FILES=(
  "SUMMARY.md"
  "DIFFSTAT.txt"
  "DIFF.patch"
  "TESTS.txt"
  "RISK.md"
)

# Use git ls-tree to check files exist on the ref without checkout
BUNDLE_COMPLETE=true
MISSING_FILES=()

for file in "${REQUIRED_FILES[@]}"; do
  FILE_PATH="$EVIDENCE_DIR/$file"
  if ! git ls-tree -r "$REF" --name-only | grep -q "^$FILE_PATH$"; then
    BUNDLE_COMPLETE=false
    MISSING_FILES+=("$file")
  fi
done

# Report results
echo "========================================="
if [ "$BUNDLE_COMPLETE" = true ]; then
  echo "PASS"
  echo "Ref: $REF"
  echo "TASK_ID: $TASK_ID"
  echo "Task file: $TASK_FILE"
  echo "Changed files: $CHANGED_COUNT"
  echo "Task scope: Enforced"
  echo "Evidence bundle: Complete"
  echo "========================================="
  exit 0
else
  echo "FAIL: Evidence bundle incomplete"
  echo "Ref: $REF"
  echo "TASK_ID: $TASK_ID"
  echo "Task file: $TASK_FILE"
  echo "Changed files: $CHANGED_COUNT"
  echo "Evidence dir: $EVIDENCE_DIR"
  echo "Missing files:"
  for file in "${MISSING_FILES[@]}"; do
    echo "  - $file"
  done
  echo "========================================="
  exit 1
fi
