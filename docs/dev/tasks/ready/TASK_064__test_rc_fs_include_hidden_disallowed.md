# TASK_064__test_rc_fs_include_hidden_disallowed.md

TASK_ID: TASK_064
Title: Test RC-FS-INCLUDE-HIDDEN-DISALLOWED
Executor: UNASSIGNED
Status: Ready
Dependencies: none

## Goal
Add test coverage asserting RC-FS-INCLUDE-HIDDEN-DISALLOWED for FS_LIST when include_hidden is requested.

## Non-goals
No policy logic changes.
Do not modify any other FS_LIST harness file (keep independent).
No edits outside ALLOWED_FILES.

## Files allowed to touch
tests/test_rc_fs_include_hidden_disallowed.sh
tests/fixtures/fs_list_include_hidden_disallowed.json
docs/dev/evidence/TASK_064/**

## Files forbidden to touch
Everything else

## Procedure
1) Locate an existing FS_LIST fixture to confirm request schema and the correct field name for include_hidden (copy structure; change only the minimum).
2) Create fixture tests/fixtures/fs_list_include_hidden_disallowed.json requesting include_hidden=true (per confirmed schema).
3) Create harness tests/test_rc_fs_include_hidden_disallowed.sh asserting DENY + RC-FS-INCLUDE-HIDDEN-DISALLOWED.

## Acceptance criteria
- Harness exits 0.
- Output includes RC-FS-INCLUDE-HIDDEN-DISALLOWED.

## Evidence required
- git diff --stat origin/main...HEAD
- git status --porcelain
- show created/modified files
- show exact command + full output for the harness/script run

## Return format
1) Summary
2) Evidence (full command outputs)
3) Notes / deviations
