# TASK_066__test_rc_fs_missing_intent_fields.md

TASK_ID: TASK_066
Title: Test RC-FS-MISSING-INTENT-FIELDS
Executor: UNASSIGNED
Status: Ready
Dependencies: none

## Goal
Add test coverage asserting RC-FS-MISSING-INTENT-FIELDS when intent fields are absent.

## Non-goals
No policy logic changes.
No edits outside ALLOWED_FILES.

## Files allowed to touch
tests/test_rc_fs_missing_intent_fields.sh
tests/fixtures/fs_missing_intent_goal.json
tests/fixtures/fs_missing_intent_expected_outputs.json
docs/dev/evidence/TASK_066/**

## Files forbidden to touch
Everything else

## Procedure
1) Locate an existing fixture that includes intent fields to confirm exact schema.
2) Create two fixtures:
- tests/fixtures/fs_missing_intent_goal.json (omit intent.goal)
- tests/fixtures/fs_missing_intent_expected_outputs.json (omit intent.expected_outputs)
3) Create harness tests/test_rc_fs_missing_intent_fields.sh that runs both fixtures and asserts DENY + RC-FS-MISSING-INTENT-FIELDS for each.

## Acceptance criteria
- Harness exits 0.
- Output includes RC-FS-MISSING-INTENT-FIELDS for both missing-field cases.

## Evidence required
- git diff --stat origin/main...HEAD
- git status --porcelain
- show created/modified files
- show exact command + full output for the harness/script run

## Return format
1) Summary
2) Evidence (full command outputs)
3) Notes / deviations
