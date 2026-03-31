#!/usr/bin/env bash
# Cecil run loop: merge first (capped), then execute own tasks (capped)

set -e
# --- BASELINE GATE (auto) BEGIN ---
if [[ -x "system/scripts/baseline-gate.sh" ]]; then
  system/scripts/baseline-gate.sh --repo "." --allow-out "out/" --salvage-prefix "origin/codex/SALVAGE_MAIN" || exit $?
else
  echo "STOP: missing baseline gate (system/scripts/baseline-gate.sh)" >&2
  exit 2
fi
# --- BASELINE GATE (auto) END ---

export GIT_PAGER=cat
export PAGER=cat
git config --global core.pager cat >/dev/null 2>&1 || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIMITS_FILE="system/ops/limits.json"
PLAN_OUTPUT="ops/CECIL_PLAN.txt"

echo "========================================="
echo "CECIL RUN LOOP"
echo "========================================="
echo ""

# Read caps from limits.json
if [ ! -f "$LIMITS_FILE" ]; then
  echo "ERROR: $LIMITS_FILE not found"
  exit 1
fi

MERGE_CAP=$(grep -o '"cecil_max_merges_per_run":[[:space:]]*[0-9]*' "$LIMITS_FILE" | grep -o '[0-9]*$')
TASK_CAP=$(grep -o '"cecil_max_tasks_per_run":[[:space:]]*[0-9]*' "$LIMITS_FILE" | grep -o '[0-9]*$')

if [ -z "$MERGE_CAP" ] || [ -z "$TASK_CAP" ]; then
  echo "ERROR: Could not read caps from $LIMITS_FILE"
  exit 1
fi

echo "Caps: Merges=$MERGE_CAP, Tasks=$TASK_CAP"
echo ""

# Ensure running from governance-layer repo root
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ "$ROOT" != "/Volumes/SSD/archive/gov/governance-layer" ]; then
  echo "ERROR: Must run from governance-layer repo root: /Volumes/SSD/archive/gov/governance-layer"
  echo "Current root: ${ROOT:-not a git repo}"
  exit 2
fi

# Phase 1: Preflight
echo "--- Phase 1: Preflight ---"
git checkout main
git fetch origin --prune
git pull --ff-only

if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: Working tree not clean"
  git status --short
  exit 1
fi

echo "Preflight: OK"
echo ""

# Phase 2: Merge
echo "--- Phase 2: Merge (limit: $MERGE_CAP) ---"
export MERGE_QUEUE_LIMIT="$MERGE_CAP"
"$SCRIPT_DIR/merge-queue.sh"
echo ""

# Phase 2.5: Task pool watermark check
echo "--- Phase 2.5: Task Pool Watermark Check ---"
WATERMARK_OUTPUT=$("$SCRIPT_DIR/task-watermark.sh" 2>&1)
echo "$WATERMARK_OUTPUT"

# Parse watermark status
PROMPT=$(echo "$WATERMARK_OUTPUT" | grep -o 'PROMPT=[01]' | cut -d= -f2)
LAST_SEED_FILE=$(echo "$WATERMARK_OUTPUT" | grep -o 'LAST_SEED_FILE=[^ ]*' | cut -d= -f2)

# Non-interactive scaffolder flow if PROMPT=1 (pool low + seed present + seed changed)
if [ "$PROMPT" = "1" ]; then
  echo ""
  echo "Ready task pool is below threshold and seed file has changed."
  echo "Seed file: docs/dev/task-seeds/SEED.md"
  if [ "$LAST_SEED_FILE" != "none" ] && [ "$LAST_SEED_FILE" != "docs/dev/task-seeds/SEED.md" ]; then
    echo "Note: Last scaffold used different seed file ($LAST_SEED_FILE)"
  fi
  echo ""
  SCAFFOLD_MODE="${CECIL_SCAFFOLD_MODE:-stop}"
  echo "Scaffolder mode: $SCAFFOLD_MODE"
  case "$SCAFFOLD_MODE" in
    stop)
      echo "STOP: Watermark prompt condition detected; set CECIL_SCAFFOLD_MODE=dry-run or CECIL_SCAFFOLD_MODE=write to continue non-interactively."
      exit 3
      ;;
    dry-run)
      DO_DRY_RUN=1
      DO_WRITE=0
      ;;
    write)
      DO_DRY_RUN=1
      DO_WRITE=1
      ;;
    *)
      echo "ERROR: Unsupported CECIL_SCAFFOLD_MODE='$SCAFFOLD_MODE' (expected: stop|dry-run|write)"
      exit 2
      ;;
  esac

  if [ "$DO_DRY_RUN" = "1" ]; then
    echo ""
    echo "Running scaffolder dry-run..."
    python3 scripts/task_scaffold.py --seed docs/dev/task-seeds/SEED.md --dry-run
    echo ""

    if [ "$DO_WRITE" = "1" ]; then
      echo ""
      echo "Creating scaffold branch..."

      # Ensure we're on clean main
      git checkout main
      git fetch origin --prune
      git pull --ff-only

      if [ -n "$(git status --porcelain)" ]; then
        echo "ERROR: Working tree not clean, cannot scaffold" >&2
        exit 1
      fi

      # Create branch with date stamp
      SCAFFOLD_DATE=$(date +%Y%m%d)
      SCAFFOLD_BRANCH="feat/seed-scaffold-$SCAFFOLD_DATE"
      git checkout -b "$SCAFFOLD_BRANCH"

      # Run scaffolder with write
      echo "Scaffolding tasks..."
      python3 scripts/task_scaffold.py \
        --seed docs/dev/task-seeds/SEED.md \
        --write \
        --emit ops/TASK_SCAFFOLD_LAST.json

      # Stage and commit
      git add docs/dev/tasks/ready/TASK_*.md ops/TASK_SCAFFOLD_LAST.json
      git commit -m "Scaffold tasks from SEED.md

Generated via Cecil runloop watermark check.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

      # Push to origin
      git push -u origin "$SCAFFOLD_BRANCH"

      echo ""
      echo "Scaffold branch created and pushed: $SCAFFOLD_BRANCH"
      echo "Created task files:"
      git --no-pager show --name-only --oneline -1 | grep TASK_
      echo ""
      echo "Branch NOT merged to main (requires manual approval)."
      echo ""

      # Return to main for task selection
      git checkout main
    else
      echo "Skipping task scaffolding write phase."
    fi
  else
    echo "Skipping scaffolder dry-run."
  fi
fi

echo ""

# Phase 3: Task selection
echo "--- Phase 3: Cecil Task Selection (limit: $TASK_CAP) ---"

NEXT_TASKS=$("$SCRIPT_DIR/queue-list-next.sh" | head -n "$TASK_CAP")

if [ -z "$NEXT_TASKS" ]; then
  echo "No READY tasks available for Cecil"
  mkdir -p ops
  cat > "$PLAN_OUTPUT" <<PLAN_EOF
CECIL EXECUTION PLAN
====================
Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Cap: $TASK_CAP tasks

Status: No READY tasks available
PLAN_EOF
  echo "Plan written to: $PLAN_OUTPUT"
  exit 0
fi

# Claim tasks and build plan
PLAN_CONTENT="CECIL EXECUTION PLAN
====================
Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Cap: $TASK_CAP tasks

Tasks:
"

TASK_COUNT=0
for TASK_ID in $NEXT_TASKS; do
  TASK_COUNT=$((TASK_COUNT + 1))
  
  # Claim task
  "$SCRIPT_DIR/queue-claim.sh" "$TASK_ID" "Cecil" >/dev/null
  
  # Find task file
  TASK_FILE=$(find docs/dev/tasks -name "${TASK_ID}__*.md" | head -n 1)
  
  if [ -z "$TASK_FILE" ]; then
    TASK_FILE="docs/dev/tasks/ready/${TASK_ID}__unknown.md"
  fi
  
  PLAN_CONTENT="${PLAN_CONTENT}
$TASK_COUNT. TASK: $TASK_ID
   File: $TASK_FILE
"
done

PLAN_CONTENT="${PLAN_CONTENT}
Total tasks: $TASK_COUNT
Status: Claimed for Cecil
"

# Write to file
mkdir -p ops
echo "$PLAN_CONTENT" > "$PLAN_OUTPUT"

# Print to stdout
echo "$PLAN_CONTENT"

echo "Plan written to: $PLAN_OUTPUT"
echo ""
echo "========================================="
echo "Cecil run loop complete"
echo "========================================="
