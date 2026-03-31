# TASK_122__docs_throughput_operator_notes_for_queue_drift_scan_and_release_gate.md

TASK_ID: TASK_122
Title: Docs: throughput operator notes for queue-drift-scan and release-gate
Executor: Cecil
Owner/Gate: Greg
Branch: codex/TASK_122
Status: Ready
Dependencies: none
Bucket: Docs / process (optional)

## Goal
Document when to run queue-drift-scan and release-gate, and how to interpret drift/pending-merge results before throughput batches.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- docs/dev/RUNBOOK.md
- docs/dev/evidence/TASK_122/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_122/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- RUNBOOK documents queue-drift-scan informational vs `--exit-on-drift` modes.
- Release-gate usage section references when to run it before merge windows.
- Evidence transcript shows the docs diff and commands used.

## Deterministic test plan (commands)
- `rg -n "queue-drift-scan|release-gate" docs/dev/RUNBOOK.md`

## Evidence required
- `docs/dev/evidence/TASK_122/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If RUNBOOK already covers these workflows at the same fidelity, close out with provenance.
- Stop if the required docs are outside the allowlist.
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
