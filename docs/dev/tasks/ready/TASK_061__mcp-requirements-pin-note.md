# TASK_061__mcp-requirements-pin-note.md

TASK_ID: TASK_061
Title: Document the mcp==1.26.0 pin rationale and where it is enforced
Executor: Cecil
Owner/Gate: Greg
Branch: feat/mcp-pin-note-061
Status: Ready
Dependencies: none

## Goal
Document why mcp is pinned to 1.26.0, where the pin lives, and how to update safely.

## Non-goals
- No dependency changes.
- No upgrades.

## Files allowed to touch
- README.md and/or mcp/README.md
- docs/dev/evidence/TASK_061/**
tests/test_rc_fs_not_a_directory.sh
tests/fixtures/fs_list_not_a_directory.json
## Files forbidden to touch
- Everything else

## Procedure
1) Assignment handshake

2) Add a short section documenting:
- Pin location
- Rationale
- Update procedure

3) Complete assignment

## Acceptance criteria
- Pin is documented in one obvious place.

## Evidence packet required
- Excerpt of updated section

## Return format
1) Summary
2) Evidence
3) Notes / deviations
