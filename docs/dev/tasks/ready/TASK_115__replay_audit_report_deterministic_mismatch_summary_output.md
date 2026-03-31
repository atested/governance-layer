# TASK_115__replay_audit_report_deterministic_mismatch_summary_output.md

TASK_ID: TASK_115
Title: Replay audit report: deterministic mismatch summary output
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_115
Status: Ready
Dependencies: TASK_114
Bucket: Replay / audit hardening

## Goal
Add a deterministic replay audit report mode or helper output that summarizes mismatches in stable order for CI and evidence use.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- scripts/replay-record.py
- tests/test_replay_audit_report.sh
- docs/dev/evidence/TASK_115/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_115/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- Replay report output is stable across repeated runs for the same mismatches.
- `tests/test_replay_audit_report.sh` validates ordering and key fields in the report.
- The feature does not weaken existing fail-closed replay exits.

## Deterministic test plan (commands)
- `bash tests/test_replay_audit_report.sh`

## Evidence required
- `docs/dev/evidence/TASK_115/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If a deterministic replay mismatch summary already exists with tests, close out with provenance.
- Stop if adding the report would require non-deterministic timestamps or environment-specific paths.
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
