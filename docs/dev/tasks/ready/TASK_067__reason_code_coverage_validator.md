# TASK_067__reason_code_coverage_validator.md

TASK_ID: TASK_067
Title: Reason code coverage validator
Executor: UNASSIGNED
Status: Ready
Dependencies: none

## Goal
Add a script that reports which RC-* reason codes present in policy evaluation logic do not have explicit test assertions.

## Non-goals
Do not change policy logic.
Do not modify docs outside the allowed files.
No edits outside ALLOWED_FILES.

## Files allowed to touch
scripts/verify-rc-coverage.py
docs/dev/evidence/TASK_067/**

## Files forbidden to touch
Everything else

## Procedure
1) Create scripts/verify-rc-coverage.py that:
- extracts RC-* tokens from policy evaluation source(s) (start with scripts/policy-eval.py)
- scans tests/ for asserted RC-* tokens
- prints missing RCs deterministically, one per line, sorted
2) Exit code:
- exit 1 if any missing RCs
- exit 0 if none missing
3) Include usage in the script header (docstring) with an exact command.

## Acceptance criteria
- Script runs deterministically and exits 1 on current main if gaps exist (expected initially).
- Script exits 0 after all RC assertion tests are merged.

## Evidence required
- git diff --stat origin/main...HEAD
- git status --porcelain
- show created/modified files
- show exact command + full output for the harness/script run

## Return format
1) Summary
2) Evidence (full command outputs)
3) Notes / deviations
