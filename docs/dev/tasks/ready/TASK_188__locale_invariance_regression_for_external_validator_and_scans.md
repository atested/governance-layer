# TASK_188__locale_invariance_regression_for_external_validator_and_scans.md

TASK_ID: TASK_188
Title: [External readiness regressions] Locale invariance regression for external validator + proof-bundle scans
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_188
Status: Ready
Dependencies: TASK_154, TASK_170
Bucket: External Usability Next
SPEC_EXPECTED: CODE

## Goal
Add a deterministic locale-invariance regression test proving external validator and proof-bundle scan outputs remain stable across `LC_ALL=C` and UTF-8 locale settings (with deterministic fallback if the UTF-8 locale is unavailable).

## Preconditions
- `system/scripts/validate-proof-bundle.sh` exists on the branch tip.
- Python 3 is available for deterministic fixture generation and SHA256 digests.

## Files allowed to touch
- tests/test_external_locale_invariance.sh
- docs/dev/evidence/TASK_188/**

## Files forbidden to touch
- Everything else

## Output expectations (Done)
- Test synthesizes or derives a deterministic proof-bundle temp directory and runs locale-variant checks twice per locale.
- Output digests are identical across repeated runs and equal across locale variants after normalization.
- Missing optional dependent scanner script(s) produce deterministic `INFO`/`SKIP` output (rc=3) without failing the test.

## Deterministic test plan
1. Build a deterministic temporary proof-bundle directory fixture (required files + optional files as needed).
2. Run validator output capture under `LC_ALL=C` twice and compare digests.
3. Run validator output capture under `LC_ALL=en_US.UTF-8` (or deterministic fallback env) twice and compare digests.
4. Compare normalized validator digests across locales.
5. If `tests/test_proof_bundle_dir_contract_scan_contract.sh` exists, run it under both locales; otherwise emit deterministic SKIP marker and continue.

## Evidence required
- docs/dev/evidence/TASK_188/TESTS.txt

## STOP conditions
- Stop if task requires edits outside allowlist.
- Stop if validator is missing on branch tip.

## Return format
1) Summary
2) Files changed
3) Locale matrix results
4) Determinism digest proof
