#!/usr/bin/env bash
# Classify unmerged codex branches as CODE or EVIDENCE_ONLY
# Usage: classify-branches.sh
# Output: Lines of format "origin/codex/TASK_XXX__hash CODE|EVIDENCE_ONLY"

set -euo pipefail

# Get all unmerged codex task branches
BRANCHES=$(git branch -r --no-merged origin/main | grep 'origin/codex/TASK_.*__' || true)

if [ -z "$BRANCHES" ]; then
  echo "No unmerged codex task branches found."
  exit 0
fi

# Classify each branch
while IFS= read -r branch; do
  branch=$(echo "$branch" | xargs)  # Trim whitespace

  # Check if any files changed outside docs/dev/evidence/
  NON_EVIDENCE=$(git diff --name-only origin/main..."$branch" 2>/dev/null | grep -v '^docs/dev/evidence/' || true)

  if [ -z "$NON_EVIDENCE" ]; then
    echo "$branch EVIDENCE_ONLY"
  else
    echo "$branch CODE"
  fi
done <<< "$BRANCHES"
