# TASK_118__queue_drift_scan_regression_tests_for_parser_and_pending_merge_detection.md

TASK_ID: TASK_118
Title: Queue drift scan: regression tests for parser and pending-merge detection
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_118
Status: Ready
Dependencies: none
Bucket: Governance tooling / gates

## Goal
Add deterministic regression tests for queue-drift-scan parser behavior, pending-merge detection, and exit code modes.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- system/scripts/queue-drift-scan.py
- tests/test_queue_drift_scan.sh
- docs/dev/evidence/TASK_118/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_118/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- `tests/test_queue_drift_scan.sh` covers parseable allowlists, anomalous allowlists, and `--exit-on-drift` exit code 2.
- Pending-merge detection is exercised with deterministic local git refs/fixtures or a controlled test mode.
- Tests are stable and do not require network flakiness tolerance.

## Deterministic test plan (commands)
- `bash tests/test_queue_drift_scan.sh`

## Evidence required
- `docs/dev/evidence/TASK_118/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If regression coverage for queue-drift-scan already exists on origin/main, close out with provenance.
- Stop if implementing tests requires mutating real remote refs instead of local/deterministic fixtures.
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
