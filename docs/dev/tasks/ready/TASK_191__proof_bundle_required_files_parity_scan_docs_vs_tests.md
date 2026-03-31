# TASK_191__proof_bundle_required_files_parity_scan_docs_vs_tests.md

TASK_ID: TASK_191
Title: [External readiness regressions] Proof-bundle required-files parity scan (docs vs tests)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_191
Status: Ready
Dependencies: TASK_148, TASK_166
Bucket: External Usability Next
SPEC_EXPECTED: CODE

## Goal
Add a deterministic parity scan that compares the required proof-bundle file set documented in `docs/EXTERNAL_CONTRACTS.md` against the required file set enforced by the existing proof-bundle required-files test.

## Preconditions
- `docs/EXTERNAL_CONTRACTS.md` exists on the branch tip.

## Files allowed to touch
- tests/test_proof_bundle_required_files_parity_scan.sh
- docs/dev/evidence/TASK_191/**

## Files forbidden to touch
- Everything else

## Output expectations (Done)
- Test extracts and sorts required-file sets from canonical docs and enforcement test source.
- If enforcement test is missing, emits deterministic `SKIP` (rc=3).
- If present, enforces set parity with deterministic PASS/FAIL markers and digest proof.

## Deterministic test plan
1. Extract required proof-bundle file names from `docs/EXTERNAL_CONTRACTS.md` (required files section).
2. Extract enforced required file names from `tests/test_proof_bundle_contract_required_files.sh` if present.
3. Compare sorted sets and print deterministic report.
4. Run twice and compare normalized stdout digests.

## Evidence required
- docs/dev/evidence/TASK_191/TESTS.txt

## STOP conditions
- Stop if task requires edits outside allowlist.

## Return format
1) Summary
2) Files changed
3) Parity scan report
4) Determinism digest proof
