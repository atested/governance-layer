# TASK_111__attestation_bundle_v1_bundle_verifier_hash_and_manifest_checks.md

TASK_ID: TASK_111
Title: Attestation bundle v1: bundle verifier (hash and manifest checks)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_111
Status: Ready
Dependencies: TASK_110
Bucket: Attestation bundle v1

## Goal
Implement a bundle verifier that validates manifest schema and file hashes for an attestation bundle v1 artifact set.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- scripts/verify-attestation-bundle.py
- tests/test_attestation_bundle_verify.sh
- tests/fixtures/attestation_bundle/**
- docs/dev/evidence/TASK_111/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_111/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- `scripts/verify-attestation-bundle.py` returns exit 0 for a valid fixture bundle and nonzero for manifest/hash mismatch.
- `tests/test_attestation_bundle_verify.sh` covers valid and invalid cases deterministically.
- Verifier output is stable and free of timestamps/random IDs.

## Deterministic test plan (commands)
- `bash tests/test_attestation_bundle_verify.sh`

## Evidence required
- `docs/dev/evidence/TASK_111/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If bundle verification already exists on origin/main with equivalent coverage, close out with provenance instead of duplicating.
- Stop if the spec would need to modify unrelated attestation semantics outside bundle verification.
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
