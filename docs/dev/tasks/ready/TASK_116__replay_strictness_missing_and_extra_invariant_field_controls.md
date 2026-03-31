# TASK_116__replay_strictness_missing_and_extra_invariant_field_controls.md

TASK_ID: TASK_116
Title: Replay strictness: missing and extra invariant field controls
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_116
Status: Ready
Dependencies: TASK_114
Bucket: Replay / audit hardening

## Goal
Harden replay comparison to test deterministic handling of missing/extra invariant fields in stored records.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- scripts/replay-record.py
- tests/test_replay.sh
- docs/dev/evidence/TASK_116/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_116/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- Replay tests cover missing invariant field and unexpected extra field cases with deterministic outputs.
- Behavior is explicitly fail-closed (or explicitly ignored) and documented in test assertions.
- No path/time dependent output appears in failures.

## Deterministic test plan (commands)
- `bash tests/test_replay.sh`

## Evidence required
- `docs/dev/evidence/TASK_116/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If origin/main already has these controls, close out with provenance.
- Stop if the task requires changing record schema ownership beyond replay verification.
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
