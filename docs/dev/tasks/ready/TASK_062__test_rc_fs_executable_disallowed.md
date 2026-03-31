# TASK_062__test_rc_fs_executable_disallowed.md

TASK_ID: TASK_062
Title: Test RC-FS-EXECUTABLE-DISALLOWED
Executor: UNASSIGNED
Status: Ready
Dependencies: none

## Goal
Add test coverage asserting RC-FS-EXECUTABLE-DISALLOWED.

## Non-goals
No policy logic changes.
No edits outside ALLOWED_FILES.

## Files allowed to touch
tests/test_rc_fs_executable_disallowed.sh
tests/fixtures/fs_write_executable_disallowed.json
docs/dev/evidence/TASK_062/**

## Files forbidden to touch
Everything else

## Procedure
1) Locate an existing FS_WRITE fixture in tests/fixtures to confirm the expected request schema. Copy its structure for this new fixture.
2) Create fixture tests/fixtures/fs_write_executable_disallowed.json changing only the minimum fields needed to request an executable write (per the confirmed schema).
3) Create harness tests/test_rc_fs_executable_disallowed.sh that runs the policy eval path used by other tests and asserts:
- decision is DENY
- reason_codes contains RC-FS-EXECUTABLE-DISALLOWED

## Acceptance criteria
- Harness exits 0.
- Output includes RC-FS-EXECUTABLE-DISALLOWED when the request asks to write an executable.

## Evidence required
- git diff --stat origin/main...HEAD
- git status --porcelain
- show created/modified files
- show exact command + full output for the harness/script run

## Return format
1) Summary
2) Evidence (full command outputs)
3) Notes / deviations
