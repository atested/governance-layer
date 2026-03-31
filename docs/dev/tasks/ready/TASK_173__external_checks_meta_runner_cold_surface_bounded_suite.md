# TASK_173__external_checks_meta_runner_cold_surface_bounded_suite.md

TASK_ID: TASK_173
Title: [External packaging tranche 2] External checks meta-runner (cold-surface bounded suite)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_173
Status: Ready
Dependencies: TASK_165, TASK_168, TASK_169, TASK_170, TASK_171, TASK_172
Bucket: External Usability Next

## Goal
Add a deterministic meta-runner that executes the bounded external packaging cold-surface checks in a stable order and emits stable per-test markers and exit codes.

## Preconditions
- Underlying check scripts exist on origin/main for TASK_165, TASK_168, TASK_169; TASK_170-172 may be present on the branch under test.

## Files allowed to touch
- tests/run_external_packaging_checks.sh
- docs/dev/evidence/TASK_173/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Meta-runner executes checks in stable order with start/end markers and propagates failures deterministically.
- Evidence transcript proves top-level digest equality across two runs.

## Deterministic test plan
1. Run `tests/run_external_packaging_checks.sh` twice (optionally with `PROOF_BUNDLE_DIR` set).
2. Assert stable test ordering markers and deterministic top-level digest.
3. Confirm optional inclusion of TASK_170 scanner when `PROOF_BUNDLE_DIR` is set.

## Evidence required
- docs/dev/evidence/TASK_173/TESTS.txt

## STOP conditions
- Stop if meta-runner requires changes to underlying check scripts outside allowlist.
- Stop if changes spill outside allowlist.

## Return format
1) Summary
2) Files changed
3) Meta-runner order and optional behavior
4) Test command(s) and exit codes
