# TASK_002__batch-plan-from-snapshot.md

TASK_ID: TASK_002
Title: Batch plan from snapshot — commit generated task stubs to repo
Executor: Cecil
Owner/Gate: Greg
Branch: feat/batch-plan-002
Status: Ready
Dependencies: TASK_001

## Goal
Take the task stubs generated in TASK_001 (by Greg via ChatGPT or equivalent),
review them for completeness and scope, and commit them as properly-formatted
task files under `docs/dev/tasks/ready/`.

## Non-goals
- No execution of any generated task.
- No code, script, or config changes.
- No changes outside `/docs/dev/**`.

## Files allowed to touch
- docs/dev/tasks/ready/TASK_*.md
- docs/dev/WORK_QUEUE.md
- docs/dev/ASSIGNMENTS.md
- docs/dev/evidence/TASK_002/**

## Files forbidden to touch
- Everything outside `/docs/dev/**`
- Existing task files (no edits to TASK_000–003)

## Procedure

Step 1 — Assignment handshake (claim)
- Add Active entry to ASSIGNMENTS.md
- Commit: `chore(assign): claim TASK_002`

Step 2 — Receive stub content from Greg
- Greg provides raw stubs (paste in task message, or as a file)
- Do not execute; validate structure only

Step 3 — Validate and format each stub
- Confirm each has: TASK_ID, Title, Executor, Goal, Non-goals, Files allowed/forbidden,
  Acceptance criteria
- Assign sequential IDs (TASK_004, TASK_005, …)
- Write each to `docs/dev/tasks/ready/TASK_NNN__slug.md`

Step 4 — Update WORK_QUEUE.md
- Add each new task to Backlog (or Next if prioritised)

Step 5 — Complete assignment handshake
- Move TASK_002 from Active to History in ASSIGNMENTS.md
- Commit: `chore(assign): complete TASK_002`

Step 6 — Docs commit
- `docs(dev): add batch-planned task stubs TASK_004–NNN`

## Acceptance criteria
- [ ] All received stubs committed as properly-formatted task files
- [ ] WORK_QUEUE.md updated with new rows
- [ ] Only `docs/dev/**` modified
- [ ] Claim first / complete last invariant satisfied

## Evidence packet required
- `git diff --stat main...HEAD`
- File list of new task stubs with line counts
- WORK_QUEUE Backlog section (paste)
- First and last commit messages
