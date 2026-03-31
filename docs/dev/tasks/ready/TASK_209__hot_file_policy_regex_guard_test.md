# TASK_209 — Hot-file policy regex guard test

SPEC_EXPECTED: CODE

## Intent
Protect hot-file policy from accidental regex drift using deterministic regression tests.

## Acceptance criteria
- Add a unit test that validates expected hot-file matches and non-matches.
- Test fails if regex behavior changes unintentionally.
- Test output is deterministic and machine-parseable.

## Files allowed to touch
- system/tests/test_hot_file_policy_regex_guard.sh
- docs/dev/evidence/TASK_209/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_209/TESTS.txt
- docs/dev/evidence/TASK_209/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_209/DIFF_STAT.txt
- docs/dev/evidence/TASK_209/HOTFILE_SCAN.txt

## Determinism expectations
- run1/run2 stdout SHA256 must match.

## STOP rules
- STOP if regex source of truth cannot be validated without editing hot files.
