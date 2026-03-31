# TASK_081__test_rc_fs_not_a_directory.md

TASK_ID: TASK_081
Title: Test RC-FS-NOT-A-DIRECTORY
Executor: Codex
Branch: codex/TASK_081
Status: Ready
Dependencies: none

## Goal
Add test coverage asserting RC-FS-NOT-A-DIRECTORY for FS_LIST when path is a file.

## Non-goals
No policy logic changes.
No edits outside ALLOWED_FILES.

## Files allowed to touch
tests/test_rc_fs_not_a_directory.sh
tests/fixtures/fs_list_not_a_directory.json
docs/dev/evidence/TASK_081/**

## Files forbidden to touch
Everything else

## Procedure
1) Locate an existing FS_LIST fixture to confirm request schema. Copy its structure for this new fixture.
2) Create fixture tests/fixtures/fs_list_not_a_directory.json pointing the list path to a known file path used by existing tests (or create a minimal test file in an existing fixture-supported way if required).
3) Create harness tests/test_rc_fs_not_a_directory.sh asserting DENY + RC-FS-NOT-A-DIRECTORY.

## Acceptance criteria
- Harness exits 0.
- Output includes RC-FS-NOT-A-DIRECTORY.

## Evidence required
- git diff --stat origin/main...HEAD
- git status --porcelain
- show created/modified files
- show exact command + full output for the harness/script run

## Return format
1) Summary
2) Evidence (full command outputs)
3) Notes / deviations
