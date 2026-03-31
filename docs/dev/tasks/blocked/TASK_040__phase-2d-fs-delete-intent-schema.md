# TASK_040__phase-2d-fs-delete-intent-schema.md

TASK_ID: TASK_040
Title: Phase 2D FS_DELETE: intent schema and normalized args design
Executor: Cecil
Owner/Gate: Greg
Branch: feat/phase-2d-fs-delete-schema-040
Status: Done
Dependencies: none

## Goal
Close out TASK_040 with evidence/provenance showing the intended deliverable is already implemented on origin/main.

## Non-goals
- No changes to code, policy-eval, or capability registry.
- No implementation.

## Files allowed to touch
- docs/dev/evidence/TASK_040/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm origin/main already contains the TASK_040 deliverable (see provenance commits below).
2) Do not modify implementation code for this reconciliation task.
3) Capture or reference existing evidence transcript under docs/dev/evidence/TASK_040/TESTS.txt if additional closeout evidence is needed.
4) Record git diff --stat origin/main...HEAD to show this branch is governance/spec/queue reconciliation only.

Provenance / Already implemented on origin/main
- ea30ab3 docs(task-040): define FS_DELETE intent schema

Rationale
- FS_DELETE intent schema documentation already exists on origin/main.

## Acceptance criteria
- The spec explicitly marks TASK_040 as an evidence-closeout/provenance reconciliation.
- Files allowed to touch is restricted to docs/dev/evidence/TASK_040/** (closeout evidence only).
- Provenance section cites origin/main commit(s) that already satisfy the original implementation intent.
- No implementation code changes are required for task completion.

## Evidence packet required
- provenance note in this spec citing origin/main commit(s)
- docs/dev/evidence/TASK_040/TESTS.txt (existing or refreshed transcript if needed)
- git diff --stat origin/main...HEAD (reconciliation branch)

## Return format
1) Summary
2) Evidence
3) Notes / deviations
