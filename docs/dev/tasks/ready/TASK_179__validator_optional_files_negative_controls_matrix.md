# TASK_179__validator_optional_files_negative_controls_matrix.md

TASK_ID: TASK_179
Title: [External validator hardening 2] Optional-file negative controls matrix (status_bundle + queue_drift JSON)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_179
Status: Ready
Dependencies: TASK_160, TASK_170
Bucket: External Usability Next
SPEC_EXPECTED: CODE

## Goal
Add a deterministic negative-controls matrix for optional proof-bundle files validated by `validate-proof-bundle.sh`, covering malformed `status_bundle.json` and `queue_drift_scan.json` while preserving optional-file absent semantics.

## Preconditions
- `system/scripts/validate-proof-bundle.sh` exists on the branch tip.

## Files allowed to touch
- tests/test_validate_proof_bundle_optional_files_negative_controls.sh
- docs/dev/evidence/TASK_179/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- system/scripts/release-gate.sh
- system/scripts/codex-unattended.sh
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Deterministic test covers present/absent optional-file behavior and malformed-linkage/version/type failures.
- Validator outputs stable markers and exit codes (`0/1`) across repeated runs.

## Deterministic test plan
1. Build or synthesize a valid proof-bundle temp directory with optional files present.
2. Run validator twice on valid optional-file case and compare output digest.
3. Run negative controls (bad `queue_drift_scan.json` linkage, bad `status_bundle.json` schema/type) twice each and compare output digests.
4. Run optional-files-absent case and assert INFO/PASS behavior remains deterministic.

## Evidence required
- docs/dev/evidence/TASK_179/TESTS.txt

## STOP conditions
- Stop if required behavior depends on edits outside allowlist.
- Stop if validator missing on branch tip.

## Return format
1) Summary
2) Files changed
3) Optional-file negative control matrix
4) Determinism digest proof

