# TASK_168__external_packaging_smoke_docs_and_required_files_scan.md

TASK_ID: TASK_168
Title: [External packaging] External packaging smoke (docs + required files scan)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_168
Status: Ready
Dependencies: none
Bucket: External Usability Next

## Goal
Add a deterministic external packaging smoke test that scans required files and documentation anchors, while treating a dirty worktree as INFO (non-failing).

## Preconditions
- Required docs/scripts for external usage exist on origin/main.

## Files allowed to touch
- tests/test_external_packaging_smoke.sh
- docs/dev/evidence/TASK_168/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/bootstrap-run.sh
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Deterministic test checks required file presence and docs references to proof-bundle required outputs.
- Dirty worktree is reported as INFO and does not fail the test.
- Transcript includes two-run digest equality of normalized output.

## Deterministic test plan
1. Run `tests/test_external_packaging_smoke.sh`.
2. Assert required files and docs references are present.
3. Assert INFO handling for dirty/clean status path.
4. Compare stdout digest across two runs.

## Evidence required
- docs/dev/evidence/TASK_168/TESTS.txt

## STOP conditions
- Stop if required file checks need to mutate the repository.
- Stop if changes spill outside the allowlist.

## Return format
1) Summary
2) Files changed
3) Packaging smoke checks enforced
4) Test command(s) and exit codes

