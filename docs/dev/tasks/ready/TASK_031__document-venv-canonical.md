# TASK_031__document-venv-canonical.md

TASK_ID: TASK_031
Title: Decide and document canonical venv location (root venv vs mcp/.venv)
Executor: Cecil
Owner/Gate: Greg
Branch: feat/canonical-venv-031
Status: Evidence Submitted
Dependencies: none

## Goal
Document a single canonical venv strategy for this repo and update docs accordingly.

## Non-goals
- Do not create or move environments.
- Do not change dependencies.

## Files allowed to touch
- README.md and/or mcp/README.md
- docs/dev/PLANNER_SNAPSHOT.md (optional if contradictory)
- docs/dev/evidence/TASK_031/**
## Files forbidden to touch
- Everything else

## Procedure
Pending merge note
Published branch pending merge: origin/codex/TASK_031__4aad760
Related origin/main provenance (partial or prior implementation context):
- 7f4c83d docs(readme): normalize canonical venv path for smoke and tools

Rationale
- Preserve CODE semantics in this spec; work exists on a published topic branch and should not be re-run until merge disposition is known.

1) Assignment handshake

2) Decide canonical venv location and document:
- Location
- How to create it
- How to run scripts/tests using it

3) Complete assignment

## Acceptance criteria
- Docs indicate a single canonical venv location and usage.
- No conflicting guidance remains in edited docs.

## Evidence packet required
- published branch pending merge: origin/codex/TASK_031__4aad760
- Excerpt of updated doc section(s)

## Return format
1) Summary
2) Evidence
3) Notes / deviations
