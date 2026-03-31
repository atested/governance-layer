# TASK_113__attestation_bundle_v1_tamper_detection_matrix_tests.md

TASK_ID: TASK_113
Title: Attestation bundle v1: tamper detection matrix tests
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_113
Status: Ready
Dependencies: TASK_111
Bucket: Attestation bundle v1

## Goal
Add a tamper matrix for attestation bundles covering manifest tamper, payload tamper, and missing-file fail-closed behavior.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- scripts/verify-attestation-bundle.py
- tests/test_attestation_bundle_tamper.sh
- tests/fixtures/attestation_bundle/**
- docs/dev/evidence/TASK_113/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_113/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- `tests/test_attestation_bundle_tamper.sh` asserts deterministic nonzero exits and clear error messages for each tamper case.
- Valid control case still passes.
- Tamper cases are fixture-based and reproducible.

## Deterministic test plan (commands)
- `bash tests/test_attestation_bundle_tamper.sh`

## Evidence required
- `docs/dev/evidence/TASK_113/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If all tamper cases are already covered by existing bundle verifier tests, close out with provenance and evidence only.
- Stop if implementing the matrix requires changing unrelated signing/verification policy semantics.
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
