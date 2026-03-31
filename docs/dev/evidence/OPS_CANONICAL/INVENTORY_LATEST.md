# Inventory Latest

## Repo

- Top: /Volumes/SSD/archive/gov/governance-layer
- Branch: cecil/OPS-CANONICAL

## Remotes

origin	git@github.com:GregKeeter/governance-layer.git (fetch)
origin	git@github.com:GregKeeter/governance-layer.git (push)

## system/scripts index

- cecil-runloop.sh — #!/usr/bin/env bash
- cecil-runloop.sh — #!/usr/bin/env bash
- codex-batch.sh — #!/usr/bin/env bash
- codex-batch.sh — #!/usr/bin/env bash
- enforce-task-scope.sh — #!/usr/bin/env bash
- enforce-task-scope.sh — #!/usr/bin/env bash
- inventory-snapshot.sh — #!/usr/bin/env bash
- inventory-snapshot.sh — #!/usr/bin/env bash
- merge-queue.sh — #!/usr/bin/env bash
- merge-queue.sh — #!/usr/bin/env bash
- queue-claim.sh — #!/usr/bin/env bash
- queue-claim.sh — #!/usr/bin/env bash
- queue-complete.sh — #!/usr/bin/env bash
- queue-complete.sh — #!/usr/bin/env bash
- queue-list-next.sh — #!/usr/bin/env bash
- queue-list-next.sh — #!/usr/bin/env bash
- task-watermark.sh — #!/usr/bin/env bash
- task-watermark.sh — #!/usr/bin/env bash
- verify-branch.sh — #!/usr/bin/env bash
- verify-branch.sh — #!/usr/bin/env bash

## Keyword detections

### WORK_QUEUE / claim / merge / ASSIGNMENTS behaviors

system/scripts/cecil-runloop.sh:139:      git checkout main
system/scripts/cecil-runloop.sh:170:# Claim tasks and build plan
system/scripts/cecil-runloop.sh:183:  # Claim task
system/scripts/cecil-runloop.sh:184:  "$SCRIPT_DIR/queue-claim.sh" "$TASK_ID" "Cecil" >/dev/null
system/scripts/cecil-runloop.sh:201:Status: Claimed for Cecil
system/scripts/cecil-runloop.sh:46:git checkout main
system/scripts/cecil-runloop.sh:62:"$SCRIPT_DIR/merge-queue.sh"
system/scripts/cecil-runloop.sh:98:      git checkout main
system/scripts/codex-batch.sh:109:   - FORBIDDEN: docs/dev/ASSIGNMENTS.md (Cecil updates this at merge time)
system/scripts/codex-batch.sh:122:Status: Ready for Codex (read-only list, no claims made)
system/scripts/codex-batch.sh:2:# Generate Codex batch run instructions (READ-ONLY: no task claiming)
system/scripts/codex-batch.sh:39:# Checkout main
system/scripts/codex-batch.sh:40:git checkout main
system/scripts/codex-batch.sh:79:# Build batch instructions (READ-ONLY: do not claim tasks here)
system/scripts/codex-batch.sh:95:  # Find task file (no claim - read-only mode)
system/scripts/enforce-task-scope.sh:100:  if [ "$changed_file" = "docs/dev/ASSIGNMENTS.md" ]; then
system/scripts/enforce-task-scope.sh:104:    echo "ERROR: docs/dev/ASSIGNMENTS.md must not be modified by task branches"
system/scripts/enforce-task-scope.sh:99:  # Hard fail on ASSIGNMENTS.md
system/scripts/inventory-snapshot.sh:43:echo "### WORK_QUEUE / claim / merge / ASSIGNMENTS behaviors" >> "$OUT"
system/scripts/inventory-snapshot.sh:46:  'WORK_QUEUE|queue-claim|claim|merge-queue|git merge|checkout main|ASSIGNMENTS\.md|Auto-resolving ASSIGNMENTS' \
system/scripts/inventory-snapshot.sh:75:grep -Rni --exclude-dir=.git --exclude='*.log' -E 'git merge|checkout main|reset --hard origin/main' system/scripts 2>/dev/null | sort | sed 's/^/- /' >> "$OUT" || true
system/scripts/merge-queue.sh:104:  if git merge --no-ff -m "Merge $CANDIDATE" "$CANDIDATE"; then
system/scripts/merge-queue.sh:114:    # Check if ONLY ASSIGNMENTS.md is conflicted
system/scripts/merge-queue.sh:115:    if [ "$UCOUNT" -eq 1 ] && [ "$UFILES" = "docs/dev/ASSIGNMENTS.md" ]; then
system/scripts/merge-queue.sh:116:      echo "Auto-resolving ASSIGNMENTS.md-only conflict with union rule..."
system/scripts/merge-queue.sh:118:      ASSIGNMENTS_FILE="docs/dev/ASSIGNMENTS.md"
system/scripts/merge-queue.sh:132:        git merge --abort
system/scripts/merge-queue.sh:142:        echo "Auto-resolved: ASSIGNMENTS.md (union merge complete)"
system/scripts/merge-queue.sh:145:        git merge --abort
system/scripts/merge-queue.sh:164:      git merge --abort
system/scripts/merge-queue.sh:175:  if ! grep -q "TASK_" docs/dev/ASSIGNMENTS.md 2>/dev/null; then
system/scripts/merge-queue.sh:176:    echo "WARNING: ASSIGNMENTS.md check inconclusive"
system/scripts/merge-queue.sh:28:# Checkout main
system/scripts/merge-queue.sh:30:git checkout main
system/scripts/merge-queue.sh:4:# Usage: merge-queue.sh
system/scripts/merge-queue.sh:85:  if git merge-base --is-ancestor "$CANDIDATE" HEAD; then
system/scripts/queue-claim.sh:16:WORK_QUEUE="docs/dev/WORK_QUEUE.md"
system/scripts/queue-claim.sh:18:if [ ! -f "$WORK_QUEUE" ]; then
system/scripts/queue-claim.sh:19:  echo "ERROR: $WORK_QUEUE not found"
system/scripts/queue-claim.sh:2:# Claim a task for an actor in WORK_QUEUE.md
system/scripts/queue-claim.sh:24:cp "$WORK_QUEUE" "$WORK_QUEUE.bak"
system/scripts/queue-claim.sh:3:# Usage: queue-claim.sh TASK_ID ACTOR
system/scripts/queue-claim.sh:30:# Simple approach: add a note that task is claimed
system/scripts/queue-claim.sh:32:echo "# Claimed: $TASK_ID by $ACTOR at $TIMESTAMP" >> "$WORK_QUEUE"
system/scripts/queue-claim.sh:34:echo "Claimed: $TASK_ID for $ACTOR"
system/scripts/queue-complete.sh:17:WORK_QUEUE="docs/dev/WORK_QUEUE.md"
system/scripts/queue-complete.sh:19:if [ ! -f "$WORK_QUEUE" ]; then
system/scripts/queue-complete.sh:2:# Mark a task as DONE in WORK_QUEUE.md
system/scripts/queue-complete.sh:20:  echo "ERROR: $WORK_QUEUE not found"
system/scripts/queue-complete.sh:25:cp "$WORK_QUEUE" "$WORK_QUEUE.bak"
system/scripts/queue-complete.sh:29:echo "# Completed: $TASK_ID ($BRANCH @ $COMMIT) at $TIMESTAMP" >> "$WORK_QUEUE"
system/scripts/queue-list-next.sh:10:  echo "ERROR: $WORK_QUEUE not found" >&2
system/scripts/queue-list-next.sh:2:# List next READY tasks from WORK_QUEUE.md "Next" section
system/scripts/queue-list-next.sh:33:done < "$WORK_QUEUE"
system/scripts/queue-list-next.sh:7:WORK_QUEUE="docs/dev/WORK_QUEUE.md"
system/scripts/queue-list-next.sh:9:if [ ! -f "$WORK_QUEUE" ]; then
system/scripts/verify-branch.sh:56:# Check for ASSIGNMENTS.md modification (should never happen, CI blocks this)
system/scripts/verify-branch.sh:57:if echo "$CHANGED_FILES" | grep -q "^docs/dev/ASSIGNMENTS.md$"; then
system/scripts/verify-branch.sh:58:  echo "FAIL: ASSIGNMENTS.md modified (policy violation)"
system/scripts/verify-branch.sh:61:  echo "Codex branches must not modify ASSIGNMENTS.md"

## Tasks (ready)

TASK_000__dev-workflow-scaffold.md
TASK_001__upload-snapshot.md
TASK_002__batch-plan-from-snapshot.md
TASK_003__dry-run-doc-task.md
TASK_010__update-active-task.md
TASK_011__update-changelog-2b1-2c2.md
TASK_012__sync-test-suite-catalogue.md
TASK_013__roadmap-position-update.md
TASK_020__phase-2d-scope-proposal.md
TASK_021__signing-phase3-spec.md
TASK_022__cross-root-promotion-design.md
TASK_030__mcp-smoke-deterministic-python.md
TASK_031__document-venv-canonical.md
TASK_032__add-smoke-failure-mode-test.md
TASK_050__verify-invariants-doc-vs-code.md
TASK_051__reason-codes-index.md
TASK_060__normalize-runtime-dir-doc.md
TASK_061__mcp-requirements-pin-note.md
TASK_062__test_rc_fs_executable_disallowed.md
TASK_063__test_rc_fs_not_a_directory.md
TASK_064__test_rc_fs_include_hidden_disallowed.md
TASK_065__test_rc_fs_not_a_file.md
TASK_066__test_rc_fs_missing_intent_fields.md
TASK_067__reason_code_coverage_validator.md

## Evidence directories

docs/dev/evidence/OPS_CANONICAL

## Policy reason codes (RC-FS-*)

- 32:RC_PATH_DISALLOWED = "RC-FS-PATH-DISALLOWED"
- 33:RC_HIDDEN_PATH = "RC-FS-HIDDEN-PATH"
- 34:RC_PATH_TRAVERSAL = "RC-FS-PATH-TRAVERSAL"
- 35:RC_OVERWRITE_DISALLOWED = "RC-FS-OVERWRITE-DISALLOWED"
- 36:RC_EXECUTABLE_DISALLOWED = "RC-FS-EXECUTABLE-DISALLOWED"
- 37:RC_NOT_A_DIRECTORY = "RC-FS-NOT-A-DIRECTORY"
- 38:RC_INCLUDE_HIDDEN_DISALLOWED = "RC-FS-INCLUDE-HIDDEN-DISALLOWED"
- 39:RC_NOT_A_FILE = "RC-FS-NOT-A-FILE"
- 40:RC_MAX_BYTES_EXCEEDED = "RC-FS-MAX-BYTES-EXCEEDED"
- 41:RC_MISSING_INTENT_FIELDS = "RC-FS-MISSING-INTENT-FIELDS"
- 42:RC_CROSS_ROOT_DISALLOWED = "RC-FS-CROSS-ROOT-DISALLOWED"
- 43:RC_RECURSIVE_DISALLOWED = "RC-FS-RECURSIVE-DISALLOWED"

## Potential contradictions

- Scripts that appear to merge or touch main (must be classified in OPS_CANONICAL):

- system/scripts/cecil-runloop.sh:139:      git checkout main
- system/scripts/cecil-runloop.sh:46:git checkout main
- system/scripts/cecil-runloop.sh:98:      git checkout main
- system/scripts/codex-batch.sh:39:# Checkout main
- system/scripts/codex-batch.sh:40:git checkout main
- system/scripts/inventory-snapshot.sh:46:  'WORK_QUEUE|queue-claim|claim|merge-queue|git merge|checkout main|ASSIGNMENTS\.md|Auto-resolving ASSIGNMENTS' \
- system/scripts/inventory-snapshot.sh:75:grep -Rni --exclude-dir=.git --exclude='*.log' -E 'git merge|checkout main|reset --hard origin/main' system/scripts 2>/dev/null | sort | sed 's/^/- /' >> "$OUT" || true
- system/scripts/merge-queue.sh:104:  if git merge --no-ff -m "Merge $CANDIDATE" "$CANDIDATE"; then
- system/scripts/merge-queue.sh:132:        git merge --abort
- system/scripts/merge-queue.sh:145:        git merge --abort
- system/scripts/merge-queue.sh:164:      git merge --abort
- system/scripts/merge-queue.sh:28:# Checkout main
- system/scripts/merge-queue.sh:30:git checkout main
- system/scripts/merge-queue.sh:85:  if git merge-base --is-ancestor "$CANDIDATE" HEAD; then
