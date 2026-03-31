# TASK_020__phase-2d-scope-proposal.md

TASK_ID: TASK_020
Title: Choose and document a single Phase 2D target (scope + tests + invariants)
Executor: Cecil
Owner/Gate: Greg
Branch: feat/phase-2d-scope-020
Status: Ready
Dependencies: none

## Goal
Create docs/dev/EPIC_PHASE_2D.md selecting exactly one Phase 2D target area and defining:
- scope and non-scope
- invariants touched
- threat delta
- test plan and expected RC codes (if applicable)

## Non-goals
- No code changes.
- No "multiple option" doc. Pick one.

## Files allowed to touch
- docs/dev/EPIC_PHASE_2D.md
- docs/dev/evidence/TASK_020/**
## Files forbidden to touch
- Everything else

## Procedure
1) Assignment handshake

2) Write docs/dev/EPIC_PHASE_2D.md
Include sections:
- Selected target (one of: FS_DELETE, EXEC, EGRESS, other clearly defined)
- Rationale (brief)
- Capability additions needed (cap registry deltas)
- Policy-eval deltas (what new checks, what new RC codes)
- MCP tool surface deltas
- Tests to add (IDs, scenarios)
- Invariants impacted (map to INV list)
- "Fail closed" boundaries

3) Complete assignment

## Acceptance criteria
- Exactly one target selected.
- Contains enough structure to derive 10–20 implementation tasks without guesswork.

## Evidence packet required
- File created path + excerpt of the "Selected target" section

## Return format
1) Summary
2) Evidence
3) Notes / deviations
