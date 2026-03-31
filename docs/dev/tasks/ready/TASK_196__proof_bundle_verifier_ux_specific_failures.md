# TASK_196 — Proof bundle verifier UX specific failures

SPEC_EXPECTED: CODE

## Intent
Improve verifier UX by producing specific failure diagnostics (exit code, file path, remediation hint) without changing hot validator script in this task.

## Acceptance criteria
- Implement non-hot wrapper/helper and tests that format deterministic failure diagnostics.
- Include explicit exit code, failed path, and a stable hint string.

## Files allowed to touch
- system/tools/proof_bundle_verifier_ux.sh
- system/tests/test_proof_bundle_verifier_ux.sh
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_196/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_196/TESTS.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_196/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_196/DIFF_STAT.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_196/HOTFILE_SCAN.txt

## Determinism expectations
- Wrapper/test output must be stable across repeated runs.

## STOP rules
- STOP if achieving UX specificity requires touching `system/scripts/validate-proof-bundle.sh`.
