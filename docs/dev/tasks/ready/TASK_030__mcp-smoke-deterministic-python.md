# TASK_030__mcp-smoke-deterministic-python.md

TASK_ID: TASK_030
Title: Make MCP smoke run deterministically without venv activation dependency
Executor: Cecil
Owner/Gate: Greg
Branch: feat/mcp-smoke-deterministic-030
Status: Done
Dependencies: none

## Goal
Close out TASK_030 with evidence/provenance showing the intended deliverable is already implemented on origin/main.

## Non-goals
- No behavior change to MCP server beyond import/launch determinism.
- No network calls.

## Files allowed to touch
- docs/dev/evidence/TASK_030/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm origin/main already contains the TASK_030 deliverable (see provenance commits below).
2) Do not modify implementation code for this reconciliation task.
3) Capture or reference existing evidence transcript under docs/dev/evidence/TASK_030/TESTS.txt if additional closeout evidence is needed.
4) Record git diff --stat origin/main...HEAD to show this branch is governance/spec/queue reconciliation only.

Provenance / Already implemented on origin/main
- 99c7f70 test(smoke): make python invocation deterministic
- c24b4e3 test(smoke): make runner portable across interpreters and runtime roots
- 397c2ad docs(smoke): align canonical command with policy runtime

Rationale
- Deterministic MCP smoke invocation and canonical command are already implemented on origin/main.

## Acceptance criteria
- The spec explicitly marks TASK_030 as an evidence-closeout/provenance reconciliation.
- Files allowed to touch is restricted to docs/dev/evidence/TASK_030/** (closeout evidence only).
- Provenance section cites origin/main commit(s) that already satisfy the original implementation intent.
- No implementation code changes are required for task completion.

## Evidence packet required
- provenance note in this spec citing origin/main commit(s)
- docs/dev/evidence/TASK_030/TESTS.txt (existing or refreshed transcript if needed)
- git diff --stat origin/main...HEAD (reconciliation branch)

## Return format
1) Summary
2) Evidence outputs
3) Notes / deviations
