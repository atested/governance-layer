# TASK_060__normalize-runtime-dir-doc.md

TASK_ID: TASK_060
Title: Normalize documentation references to GOV_RUNTIME_DIR and runtime layout
Executor: Cecil
Owner/Gate: Greg
Branch: feat/runtime-doc-normalize-060
Status: Ready
Dependencies: none

## Goal
Ensure docs consistently reference the runtime directory and GOV_RUNTIME_DIR semantics.

## Non-goals
- No behavior change.
- No code changes.

## Files allowed to touch
- README.md and/or relevant docs under docs/**
- docs/dev/PLANNER_SNAPSHOT.md (optional if contradictory)
- docs/dev/evidence/TASK_060/**
## Files forbidden to touch
- Everything else

## Procedure
1) Assignment handshake

2) Update docs to:
- Use GOV_RUNTIME_DIR consistently
- Describe runtime file layout briefly

3) Complete assignment

## Acceptance criteria
- No contradictory runtime dir guidance remains in edited docs.

## Evidence packet required
- Excerpts of updated sections

## Return format
1) Summary
2) Evidence
3) Notes / deviations
