# TASK_175__validator_negative_controls_matrix_required_files_and_checksum.md

TASK_ID: TASK_175
Title: [External validator hardening] Validator negative-controls matrix (required files + checksum)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_175
Status: Ready
Dependencies: TASK_154
Bucket: External Validator Hardening
SPEC_EXPECTED: CODE

## Goal
Add a deterministic negative-controls matrix test for `system/scripts/validate-proof-bundle.sh` covering required-file absence, checksum mismatch, and malformed checksum-file formats.

## Preconditions
- `system/scripts/validate-proof-bundle.sh` exists on the branch tip.
- Temporary proof-bundle directories can be created under `/tmp` during tests.

## Files allowed to touch
- tests/test_validate_proof_bundle_negative_controls.sh
- docs/dev/evidence/TASK_175/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- system/scripts/release-gate.sh
- system/scripts/codex-unattended.sh
- system/scripts/validate-proof-bundle.sh
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- `tests/test_validate_proof_bundle_negative_controls.sh` exercises deterministic validator FAIL paths for required-file and checksum contract violations.
- Test output includes stable markers and deterministic SHA256 digests across two runs for representative cases.
- Evidence transcript records commands, exit codes, and digest equality.

## Deterministic test plan
1. Build temporary proof-bundle fixtures under `/tmp` for each negative-control case.
2. Run validator per case twice and hash normalized stdout/stderr blocks.
3. Assert exit code `1` for contract violations and stable failure markers.

## Evidence required
- docs/dev/evidence/TASK_175/TESTS.txt

## STOP conditions
- Stop if `system/scripts/validate-proof-bundle.sh` is missing on the branch tip (dependency TASK_154 not merged).
- Stop if implementation requires edits outside allowlist.
- Stop if deterministic markers cannot be produced without changing validator behavior (requires a separate task).

## Return format
1) Summary
2) Files changed
3) Negative-control cases + exit codes
4) Determinism digest proof
