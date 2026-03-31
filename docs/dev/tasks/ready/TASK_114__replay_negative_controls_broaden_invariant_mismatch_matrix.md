# TASK_114__replay_negative_controls_broaden_invariant_mismatch_matrix.md

TASK_ID: TASK_114
Title: Replay negative controls: broaden invariant mismatch matrix
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_114
Status: Ready
Dependencies: none
Bucket: Replay / audit hardening

## Goal
Expand replay negative controls to cover more invariant mismatches beyond the current request-hash and cap-registry drift checks.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- scripts/replay-record.py
- tests/test_replay.sh
- docs/dev/evidence/TASK_114/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_114/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- `tests/test_replay.sh` (or a new companion test) includes at least two new deterministic negative controls (e.g., reason_code order mismatch, normalized_args mismatch).
- Replay exits fail-closed with stable codes/messages for new cases.
- Existing replay tests remain green.

## Deterministic test plan (commands)
- `bash tests/test_replay.sh`

## Evidence required
- `docs/dev/evidence/TASK_114/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If equivalent negative controls are already present on origin/main, close out with provenance instead of duplicating.
- Stop if the change would require broad replay format redesign rather than targeted invariant checks.
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
