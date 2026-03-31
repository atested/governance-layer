#!/usr/bin/env bash
# Generate Codex batch run instructions (READ-ONLY: no task claiming)
# Generates ops/CODEX_BATCH.txt with next available tasks

set -e

export GIT_PAGER=cat
export PAGER=cat
git config --global core.pager cat >/dev/null 2>&1 || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIMITS_FILE="system/ops/limits.json"
BATCH_OUTPUT="ops/CODEX_BATCH.txt"

# Read cap from limits.json
if [ ! -f "$LIMITS_FILE" ]; then
  echo "ERROR: $LIMITS_FILE not found"
  exit 1
fi

CAP=$(grep -o '"codex_max_tasks_per_run":[[:space:]]*[0-9]*' "$LIMITS_FILE" | grep -o '[0-9]*$')
if [ -z "$CAP" ]; then
  echo "ERROR: Could not read codex_max_tasks_per_run from $LIMITS_FILE"
  exit 1
fi

echo "Codex batch generation (cap: $CAP)"
echo ""

# Preflight: ensure clean repo state (ops/CODEX_BATCH.txt is tracked, changes are OK)
echo "--- Preflight ---"

# Ensure we're in a git repo
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "ERROR: Not in a git repository"
  exit 1
fi

# Branch-respecting mode: operate on current checked-out branch/worktree.
# No implicit checkout/reset/pull should occur here.

# Verify clean working tree (allow Codex artifacts only)
PORCELAIN=$(git status --porcelain)
if [ -n "$PORCELAIN" ]; then
  # Allowed patterns:
  # - ops/CODEX_BATCH.txt (modified or untracked)
  # - untracked .codex/ entries
  REMAINING=$(printf '%s\n' "$PORCELAIN" | grep -Ev '^( M ops/CODEX_BATCH\.txt|\?\? ops/CODEX_BATCH\.txt|\?\? \.codex/.*|\?\? \.codex/)$' || true)
  if [ -n "$REMAINING" ]; then
    echo "ERROR: Working tree not clean"
    echo "Allowed: ops/CODEX_BATCH.txt (modified/untracked), and untracked .codex/ entries"
    echo "Found:"
    echo "$REMAINING"
    exit 1
  fi
fi

echo "Preflight: OK"
echo ""

# Determine whether a task spec can run unattended in Codex lane.
is_codex_executable_task() {
  local task_id="$1"
  local task_file
  task_file=$(find docs/dev/tasks/ready -maxdepth 1 -type f -name "${task_id}__*.md" | head -n 1)
  [ -n "$task_file" ] || return 1

  # Must be explicitly assigned to Codex.
  if ! grep -Eiq '^Executor:[[:space:]]*Codex[[:space:]]*$' "$task_file"; then
    return 1
  fi

  # Exclude manual/non-branchable tasks.
  if grep -Eiq '^Branch:[[:space:]]*n/a([[:space:]]|$)' "$task_file"; then
    return 1
  fi

  # Must include an allowlist header that unattended parser supports.
  if ! grep -Eiq '^##[[:space:]]*(Allowed Files|Files allowed to touch)[[:space:]]*$' "$task_file"; then
    return 1
  fi

  return 0
}

# Get next tasks and keep only Codex-executable entries.
NEXT_TASKS_RAW=$("$SCRIPT_DIR/queue-list-next.sh")
NEXT_TASKS=""
for TASK_ID in $NEXT_TASKS_RAW; do
  if is_codex_executable_task "$TASK_ID"; then
    NEXT_TASKS="${NEXT_TASKS} ${TASK_ID}"
  fi
done
NEXT_TASKS="$(printf '%s\n' "$NEXT_TASKS" | xargs -n1 2>/dev/null | head -n "$CAP" || true)"

if [ -z "$NEXT_TASKS" ]; then
  echo "No Codex-executable READY tasks available"
  mkdir -p ops
  cat > "$BATCH_OUTPUT" <<'BATCH_EOF'
CODEX RUN BATCH
================
Status: No Codex-executable READY tasks available
BATCH_EOF
  exit 0
fi

# Build batch instructions (READ-ONLY: do not claim tasks here)
BATCH_CONTENT="CODEX RUN BATCH
================
Cap: $CAP tasks

Instructions for Codex:
For each task below, create a branch, implement changes within allowed files only,
generate evidence bundle, and push to origin.

Tasks:
"

TASK_COUNT=0
for TASK_ID in $NEXT_TASKS; do
  TASK_COUNT=$((TASK_COUNT + 1))

  # Find task file (no claim - read-only mode)
  TASK_FILE=$(find docs/dev/tasks -name "${TASK_ID}__*.md" | head -n 1)
  
  if [ -z "$TASK_FILE" ]; then
    TASK_FILE="docs/dev/tasks/ready/${TASK_ID}__unknown.md"
  fi
  
  BATCH_CONTENT="${BATCH_CONTENT}
$TASK_COUNT. TASK: $TASK_ID
   File: $TASK_FILE
   Branch: codex/$TASK_ID
   
   Requirements:
   - Only modify files in task's \"Files allowed to touch\" section
   - FORBIDDEN: docs/dev/ASSIGNMENTS.md (Cecil updates this at merge time)
   - Generate complete evidence bundle in docs/dev/evidence/$TASK_ID/
     * SUMMARY.md
     * DIFFSTAT.txt
     * DIFF.patch
     * TESTS.txt
     * RISK.md
   - Push to origin when complete
"
done

BATCH_CONTENT="${BATCH_CONTENT}
Total tasks: $TASK_COUNT
Status: Ready for Codex (read-only list, no claims made)
"

# Write to file
mkdir -p ops
echo "$BATCH_CONTENT" > "$BATCH_OUTPUT"

# Print to stdout
echo "$BATCH_CONTENT"

echo ""
echo "Batch written to: $BATCH_OUTPUT"
