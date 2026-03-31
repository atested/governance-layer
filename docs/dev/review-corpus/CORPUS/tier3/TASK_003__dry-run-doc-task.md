# TASK_003__dry-run-doc-task.md

TASK_ID: TASK_003
Title: Dry-run doc task — practice workflow end-to-end
Executor: Cecil
Owner/Gate: Greg
Branch: feat/dry-run-doc-003
Status: Ready
Dependencies: TASK_000

## Goal
Execute a minimal documentation-only task end-to-end using the full workflow:
assignment handshake, branch, file change, evidence packet, merge gate review.
Purpose: validate that the workflow machinery works before any code tasks run.

## Non-goals
- No code, script, config, or MCP changes.
- No changes outside `/docs/dev/**`.
- The content change must be trivial (e.g. update a single doc field).

## Files allowed to touch
- `/docs/dev/WORK_QUEUE.md` (add a comment row or update a status)
- `/docs/dev/ASSIGNMENTS.md` (claim/complete)
- docs/dev/evidence/TASK_003/**
## Files forbidden to touch
- Everything outside `/docs/dev/**`
- `PLANNER_SNAPSHOT.md`, `TASK_TEMPLATE.md`, `MERGE_GATE.md` (read-only for this task)

## Change budget
- Max 1 file changed (beyond ASSIGNMENTS.md)
- Max 5 lines changed in that file

## Procedure

Step 1 — Assignment handshake (claim)
- Add Active entry to ASSIGNMENTS.md
- Commit: `chore(assign): claim TASK_003`

Step 2 — Make a trivial doc change
- Add a comment line or update a status field in `WORK_QUEUE.md`
- The change must be observable and machine-verifiable (git diff shows it)

Step 3 — Commit the change
- `docs(dev): dry-run doc change for TASK_003`

Step 4 — Complete assignment handshake
- Move TASK_003 Active → History in ASSIGNMENTS.md
- Commit: `chore(assign): complete TASK_003`

Step 5 — Submit evidence and await gate review

## Acceptance criteria
- [ ] Branch created, first commit is claim, last commit is complete
- [ ] Exactly 1 non-ASSIGNMENTS file modified, ≤ 5 lines changed
- [ ] Full evidence packet provided
- [ ] Gate review passes MERGE_GATE.md checklist

## Evidence packet required
- `git status` (clean on branch)
- `git diff --stat main...HEAD`
- `git log --oneline main..HEAD` (should show exactly 3 commits: claim, change, complete)
- File list with line counts
- ASSIGNMENTS.md Active / History paste
- Diff of the changed file (inline)

## Notes
This task exists solely to validate the workflow. The specific content change is
at executor's discretion — the change itself does not matter; the process does.
