# TASK_121__policy_completeness_deterministic_rc_matrix_regression_for_core_fs_intents.md

TASK_ID: TASK_121
Title: Policy completeness: deterministic RC matrix regression for core FS intents
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_121
Status: Ready
Dependencies: none
Bucket: MCP smoke + policy completeness

## Goal
Add a deterministic regression test matrix that checks reason-code coverage/ordering for core FS intents across representative DENY cases.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- scripts/policy-eval.py
- tests/test_policy_rc_matrix.sh
- tests/fixtures/**
- docs/dev/evidence/TASK_121/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_121/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- `tests/test_policy_rc_matrix.sh` validates deterministic RC presence/order for a bounded set of fixtures.
- At least one non-evidence file changes (test and/or policy evaluator helper) to implement the matrix.
- Test output is stable across repeated runs.

## Deterministic test plan (commands)
- `bash tests/test_policy_rc_matrix.sh`

## Evidence required
- `docs/dev/evidence/TASK_121/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If equivalent RC matrix coverage already exists, close out with provenance.
- Stop if proposed fixtures duplicate existing tests without adding new deterministic assertions.
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
