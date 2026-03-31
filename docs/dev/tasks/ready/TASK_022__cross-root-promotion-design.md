# TASK_022__cross-root-promotion-design.md

TASK_ID: TASK_022
Title: Design sanctioned cross-root promotion workflow (without enabling arbitrary cross-root move)
Executor: Cecil
Owner/Gate: Greg
Branch: feat/promotion-design-022
Status: Evidence Submitted
Dependencies: none

## Goal
Create docs/dev/EPIC_PROMOTION.md defining a safe promotion path that preserves:
- cross-root deny invariant for FS_MOVE
- audit trail and intent binding
- bounded, explicit workflow

## Non-goals
- No code.
- Do not weaken cross-root FS_MOVE deny.

## Files allowed to touch
- docs/dev/EPIC_PROMOTION.md
- docs/dev/evidence/TASK_022/**
## Files forbidden to touch
- Everything else

## Procedure
Pending merge note
Published branch pending merge: origin/codex/TASK_022__53c6c2e
Related origin/main provenance (partial or prior implementation context):
- 34163d7 docs(promotion): define bounded cross-root promotion design

Rationale
- Preserve CODE semantics in this spec; work exists on a published topic branch and should not be re-run until merge disposition is known.

1) Assignment handshake

2) Write docs/dev/EPIC_PROMOTION.md
Include:
- Why FS_MOVE cross-root stays denied
- Promotion as distinct capability or guarded procedure
- Required fields (intent, src/dst roots, hashes, allowlists)
- Failure modes and RC codes
- Tests required

3) Complete assignment

## Acceptance criteria
- Keeps FS_MOVE cross-root denied.
- Defines a bounded alternative with explicit invariants.

## Evidence packet required
- published branch pending merge: origin/codex/TASK_022__53c6c2e
- File path + excerpt of workflow and failure modes

## Return format
1) Summary
2) Evidence
3) Notes / deviations
