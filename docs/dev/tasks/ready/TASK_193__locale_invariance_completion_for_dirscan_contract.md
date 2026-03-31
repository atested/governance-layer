# TASK_193 — Locale invariance completion for dirscan contract

SPEC_EXPECTED: CODE

## Goal
Enforce locale invariance regression across validator and dirscan contract outputs with deterministic run1/run2 digests and cross-locale equality.

## Preconditions
- Run from repo root.
- `tests/test_external_locale_invariance.sh` exists on branch tip.
- Determine whether `tests/test_proof_bundle_dir_contract_scan_contract.sh` exists on branch tip before enforcing dirscan locale parity.

## Files allowed to touch
- tests/test_external_locale_invariance.sh
- docs/dev/evidence/TASK_193/**

## Files forbidden to touch
- Everything else

## Evidence required
- `docs/dev/evidence/TASK_193/TESTS.txt`
- Include commands, exit codes, per-locale digests, cross-locale equality assertions, and overall run1/run2 determinism digest.

## Determinism requirement
- Run the test twice and show identical SHA256 digests for normalized output.
- Normalize absolute temp paths and run-id/path-bearing fragments before hashing.

## Procedure
1. Precheck whether `tests/test_proof_bundle_dir_contract_scan_contract.sh` exists on branch tip.
2. Update `tests/test_external_locale_invariance.sh` to:
   - enforce validator locale invariance (C vs UTF-8 locale)
   - enforce dirscan locale invariance if the dirscan contract test exists
   - otherwise emit deterministic INFO/SKIP (`rc=3`) for the dirscan subcheck only
3. Run twice and capture evidence transcript.

## STOP conditions
- STOP if implementation requires editing any file outside the allowlist.
- Do not create new dirscan tests in this task; if dirscan contract test is absent, use deterministic INFO/SKIP behavior only.

## Done when
- Validator locale invariance is enforced and deterministic.
- Dirscan locale parity is enforced when available, otherwise deterministic INFO/SKIP is recorded.
- Evidence transcript is recorded under the required path.
