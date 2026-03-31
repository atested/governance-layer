#!/usr/bin/env bash
# List unmerged CODE branches (branches that change files outside docs/dev/evidence/)
# Usage: list-code-branches.sh
# Output: One branch per line, format "origin/codex/TASK_XXX__hash"

set -euo pipefail

# Get all unmerged codex task branches
BRANCHES=$(git branch -r --no-merged origin/main | grep 'origin/codex/TASK_.*__' || true)

if [ -z "$BRANCHES" ]; then
  exit 0
fi

# Filter to CODE branches only
while IFS= read -r branch; do
  branch=$(echo "$branch" | xargs)  # Trim whitespace

  # Check if any files changed outside docs/dev/evidence/
  NON_EVIDENCE=$(git diff --name-only origin/main..."$branch" 2>/dev/null | grep -v '^docs/dev/evidence/' || true)

  if [ -n "$NON_EVIDENCE" ]; then
    echo "$branch"
  fi
done <<< "$BRANCHES"
