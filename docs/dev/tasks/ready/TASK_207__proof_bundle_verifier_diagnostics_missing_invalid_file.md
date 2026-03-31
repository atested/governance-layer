# TASK_207 — Proof bundle verifier diagnostics missing/invalid file

SPEC_EXPECTED: CODE

## Intent
Add non-hot diagnostics helper that reports exactly which proof-bundle file is missing or invalid.

## Acceptance criteria
- Helper prints stable fields: `EXIT_CODE`, `FAILED_PATH`, `DIAGNOSTIC`, `HINT`.
- No change to core hot validator behavior in this task.
- Deterministic test covers missing-file and invalid-file cases.

## Files allowed to touch
- system/tools/proof_bundle_verifier_diagnostics.sh
- system/tests/test_proof_bundle_verifier_diagnostics.sh
- docs/dev/evidence/TASK_207/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_207/TESTS.txt
- docs/dev/evidence/TASK_207/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_207/DIFF_STAT.txt
- docs/dev/evidence/TASK_207/HOTFILE_SCAN.txt

## Determinism expectations
- run1/run2 stdout SHA256 must match.

## STOP rules
- STOP if implementation requires touching `system/scripts/validate-proof-bundle.sh`.
