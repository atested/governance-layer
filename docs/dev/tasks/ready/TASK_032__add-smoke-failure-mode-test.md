# TASK_032__add-smoke-failure-mode-test.md

TASK_ID: TASK_032
Title: Add a smoke failure-mode test and prove the deterministic fix prevents it
Executor: Cecil
Owner/Gate: Greg
Branch: feat/smoke-failure-mode-032
Status: Done
Dependencies: TASK_030 (recommended)

## Goal
Close out TASK_032 with evidence/provenance showing the intended deliverable is already implemented on origin/main.

## Non-goals
- No flaky tests.
- No external dependencies.

## Files allowed to touch
- docs/dev/evidence/TASK_032/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm origin/main already contains the TASK_032 deliverable (see provenance commits below).
2) Do not modify implementation code for this reconciliation task.
3) Capture or reference existing evidence transcript under docs/dev/evidence/TASK_032/TESTS.txt if additional closeout evidence is needed.
4) Record git diff --stat origin/main...HEAD to show this branch is governance/spec/queue reconciliation only.

Provenance / Already implemented on origin/main
- 99c7f70 test(smoke): make python invocation deterministic
- c24b4e3 test(smoke): make runner portable across interpreters and runtime roots

Rationale
- The prior smoke failure mode (interpreter/activation dependency) is already addressed and demonstrably covered by the deterministic smoke runner changes on origin/main.

## Acceptance criteria
- The spec explicitly marks TASK_032 as an evidence-closeout/provenance reconciliation.
- Files allowed to touch is restricted to docs/dev/evidence/TASK_032/** (closeout evidence only).
- Provenance section cites origin/main commit(s) that already satisfy the original implementation intent.
- No implementation code changes are required for task completion.

## Evidence packet required
- provenance note in this spec citing origin/main commit(s)
- docs/dev/evidence/TASK_032/TESTS.txt (existing or refreshed transcript if needed)
- git diff --stat origin/main...HEAD (reconciliation branch)

## Return format
1) Summary
2) Evidence outputs
3) Notes / deviations
