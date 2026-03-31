# TASK_095__test_rc_fs_not_a_file.md

TASK_ID: TASK_095
Title: Test RC-FS-NOT-A-FILE
Executor: Codex
Branch: codex/TASK_095
Status: Evidence Submitted
Dependencies: none

## Goal
Add test coverage asserting RC-FS-NOT-A-FILE for FS_READ when path is a directory.

## Non-goals
No policy logic changes.
No edits outside ALLOWED_FILES.

## Files allowed to touch
- tests/test_rc_fs_not_a_file.sh
- tests/fixtures/fs_read_not_a_file.json
- docs/dev/evidence/TASK_095/**

## Files forbidden to touch
Everything else

## Procedure
Pending merge note
Published branch pending merge: origin/codex/TASK_095__061b9e3
Related origin/main provenance (partial or prior implementation context):
- 023a513 TASK_095: implement

Rationale
- Preserve CODE semantics in this spec; work exists on a published topic branch and should not be re-run until merge disposition is known.

1) Locate an existing FS_READ fixture to confirm request schema. Copy its structure.
2) Create fixture tests/fixtures/fs_read_not_a_file.json setting the read path to a directory path known to exist in the test environment (prefer a directory already used by tests).
3) Create harness tests/test_rc_fs_not_a_file.sh asserting DENY + RC-FS-NOT-A-FILE.

## Acceptance criteria
- Harness exits 0.
- Output includes RC-FS-NOT-A-FILE.

## Evidence required
- published branch pending merge: origin/codex/TASK_095__061b9e3
- git diff --stat origin/main...HEAD
- git status --porcelain
- show created/modified files
- show exact command + full output for the harness/script run

## Return format
1) Summary
2) Evidence (full command outputs)
3) Notes / deviations
