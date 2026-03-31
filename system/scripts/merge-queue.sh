#!/usr/bin/env bash
# Merge queue: verify and merge passing Codex branches to main
# Must be run by Cecil from governance-layer repo
# Usage: merge-queue.sh

set -e

export GIT_PAGER=cat
export PAGER=cat
git config --global core.pager cat >/dev/null 2>&1 || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY_SCRIPT="$SCRIPT_DIR/verify-branch.sh"

if [ ! -x "$VERIFY_SCRIPT" ]; then
  echo "ERROR: verify-branch.sh not found or not executable"
  exit 1
fi

# Ensure running from governance-layer repo root
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ "$ROOT" != "/Volumes/SSD/archive/gov/governance-layer" ]; then
  echo "ERROR: Must run from governance-layer repo root: /Volumes/SSD/archive/gov/governance-layer"
  echo "Current root: ${ROOT:-not a git repo}"
  exit 2
fi

# Checkout main
echo "Checking out main..."
git checkout main

# Fetch and update
echo "Fetching from origin..."
git fetch origin --prune

echo "Updating main..."
git pull --ff-only

# Verify clean working tree
if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: Working tree not clean"
  git status --short
  exit 1
fi

echo "Working tree clean. Proceeding..."

# Find all codex branches
CANDIDATES=$(git branch -r | grep 'origin/codex/TASK_' | sed 's/^ *//' | sort -V || true)

if [ -z "$CANDIDATES" ]; then
  echo "No codex/TASK_* branches found."
  exit 0
fi

# Track results
MERGED=()
SKIPPED=()
FAILED=()
CONFLICT_STOPPED=()

# Read merge limit from environment variable (optional)
MERGE_LIMIT="${MERGE_QUEUE_LIMIT:-0}"
MERGE_COUNT=0

echo ""
echo "========================================="
echo "Processing $(echo "$CANDIDATES" | wc -l) candidate branches..."
if [ "$MERGE_LIMIT" -gt 0 ]; then
  echo "Merge limit: $MERGE_LIMIT"
fi
echo "========================================="
echo ""

for CANDIDATE in $CANDIDATES; do
  # Check merge limit
  if [ "$MERGE_LIMIT" -gt 0 ] && [ "$MERGE_COUNT" -ge "$MERGE_LIMIT" ]; then
    echo "Merge limit reached ($MERGE_LIMIT). Stopping queue processing."
    break
  fi

  echo "--- Checking: $CANDIDATE ---"
  
  # Skip if already merged
  if git merge-base --is-ancestor "$CANDIDATE" HEAD; then
    echo "SKIP: Already merged"
    SKIPPED+=("$CANDIDATE")
    echo ""
    continue
  fi
  
  # Verify
  if "$VERIFY_SCRIPT" "$CANDIDATE"; then
    echo "Verification: PASS"
  else
    echo "Verification: FAIL"
    FAILED+=("$CANDIDATE")
    echo ""
    continue
  fi
  
  # Attempt merge
  echo "Merging $CANDIDATE..."
  if git merge --no-ff -m "Merge $CANDIDATE" "$CANDIDATE"; then
    echo "Merge: clean (no conflicts)"
  else
    # Handle conflicts
    echo "Merge: conflicts detected"

    # Detect all unmerged files
    UFILES=$(git --no-pager diff --name-only --diff-filter=U)
    UCOUNT=$(echo "$UFILES" | grep -c . || echo 0)

    # Check if ONLY ASSIGNMENTS.md is conflicted
    if [ "$UCOUNT" -eq 1 ] && [ "$UFILES" = "docs/dev/ASSIGNMENTS.md" ]; then
      echo "Auto-resolving ASSIGNMENTS.md-only conflict with union rule..."

      ASSIGNMENTS_FILE="docs/dev/ASSIGNMENTS.md"

      # Apply union merge: remove conflict markers, keep both HEAD and incoming sections
      # This preserves all History rows from both sides (union property)
      sed -e '/^<<<<<<< HEAD$/d' \
          -e '/^=======$/d' \
          -e '/^>>>>>>> /d' \
          "$ASSIGNMENTS_FILE" > "$ASSIGNMENTS_FILE.resolved"

      mv "$ASSIGNMENTS_FILE.resolved" "$ASSIGNMENTS_FILE"

      # Verify conflict markers are gone
      if grep -q '^<<<<<<<\|^=======\|^>>>>>>>' "$ASSIGNMENTS_FILE"; then
        echo "ERROR: Conflict markers still present after resolution"
        git merge --abort
        CONFLICT_STOPPED+=("$CANDIDATE")
        echo ""
        continue
      fi

      git add "$ASSIGNMENTS_FILE"

      # Complete the merge with a commit
      if git commit -m "Merge $CANDIDATE"; then
        echo "Auto-resolved: ASSIGNMENTS.md (union merge complete)"
      else
        echo "ERROR: Commit failed after conflict resolution"
        git merge --abort
        CONFLICT_STOPPED+=("$CANDIDATE")
        echo ""
        continue
      fi

    else
      # Multiple files or non-ASSIGNMENTS conflicts - stop
      echo "ERROR: Cannot auto-resolve conflicts"
      echo "Branch: $CANDIDATE"
      echo "Unmerged files ($UCOUNT):"
      echo "$UFILES"
      echo ""
      echo "Manual resolution required:"
      echo "1. Resolve conflicts in listed files"
      echo "2. git add <resolved-files>"
      echo "3. git commit"
      echo ""
      echo "Aborting merge and stopping queue."
      git merge --abort
      CONFLICT_STOPPED+=("$CANDIDATE")
      echo ""
      continue
    fi
  fi
  
  # Post-merge checks
  echo "Post-merge checks..."
  git --no-pager show --name-only --oneline -1
  
  if ! grep -q "TASK_" docs/dev/ASSIGNMENTS.md 2>/dev/null; then
    echo "WARNING: ASSIGNMENTS.md check inconclusive"
  fi
  
  if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: Working tree not clean after merge"
    git status --short
    exit 1
  fi
  
  # Push
  echo "Pushing to origin..."
  git push origin main
  
  COMMIT_HASH=$(git rev-parse --short HEAD)
  MERGED+=("$CANDIDATE ($COMMIT_HASH)")
  MERGE_COUNT=$((MERGE_COUNT + 1))
  echo "SUCCESS: Merged and pushed"
  echo ""
done

# Print summary
echo ""
echo "========================================="
echo "MERGE QUEUE SUMMARY"
echo "========================================="
echo ""

echo "MERGED (${#MERGED[@]}):"
if [ ${#MERGED[@]} -eq 0 ]; then
  echo "  (none)"
else
  for item in "${MERGED[@]}"; do
    echo "  ✓ $item"
  done
fi
echo ""

echo "SKIPPED - Already Merged (${#SKIPPED[@]}):"
if [ ${#SKIPPED[@]} -eq 0 ]; then
  echo "  (none)"
else
  for item in "${SKIPPED[@]}"; do
    echo "  - $item"
  done
fi
echo ""

echo "FAILED - Verification Failed (${#FAILED[@]}):"
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "  (none)"
else
  for item in "${FAILED[@]}"; do
    echo "  ✗ $item"
  done
fi
echo ""

echo "STOPPED - Merge Conflicts (${#CONFLICT_STOPPED[@]}):"
if [ ${#CONFLICT_STOPPED[@]} -eq 0 ]; then
  echo "  (none)"
else
  for item in "${CONFLICT_STOPPED[@]}"; do
    echo "  ! $item"
  done
fi
echo ""

echo "========================================="
echo "Queue processing complete."
echo "========================================="
