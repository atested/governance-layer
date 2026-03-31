#!/usr/bin/env bash
# Pre-commit hook: prevent codex branches from modifying ASSIGNMENTS.md
# Optional helper - not auto-installed

set -e

BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "")

if [[ "$BRANCH" =~ ^codex/ ]]; then
  STAGED_FILES=$(git diff --cached --name-only)
  
  if echo "$STAGED_FILES" | grep -q "^docs/dev/ASSIGNMENTS.md$"; then
    echo "ERROR: Codex branches must not modify docs/dev/ASSIGNMENTS.md"
    echo "Cecil updates ASSIGNMENTS on main at merge time."
    exit 1
  fi
fi

exit 0
