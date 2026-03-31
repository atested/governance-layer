# TASK_117__queue_drift_scan_informational_integration_in_project_status.md

TASK_ID: TASK_117
Title: Queue drift scan: informational integration in project-status
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_117
Status: Ready
Dependencies: none
Bucket: Governance tooling / gates

## Goal
Integrate queue-drift-scan into project-status in informational mode so drift is surfaced without gating throughput execution.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- system/scripts/project-status.sh
- system/scripts/queue-drift-scan.py
- docs/dev/evidence/TASK_117/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_117/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- `system/scripts/project-status.sh` runs `queue-drift-scan.py` in non-failing informational mode when available.
- Project status output remains deterministic and stable when drift is present.
- A regression check/test command verifies the integration path exits 0.

## Deterministic test plan (commands)
- `bash system/scripts/project-status.sh | sed -n "1,220p"`

## Evidence required
- `docs/dev/evidence/TASK_117/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If project-status already integrates queue-drift-scan in informational mode, close out with provenance.
- Stop if the only viable integration would make project-status fail hard by default.
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
