# TASK_177__validator_summary_json_contract_enforcement_tests.md

TASK_ID: TASK_177
Title: [External validator hardening] Summary JSON contract enforcement tests
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_177
Status: Ready
Dependencies: TASK_157, TASK_162
Bucket: External Validator Hardening
SPEC_EXPECTED: CODE

## Goal
Add deterministic contract tests for `validate-proof-bundle.sh --summary-json`, enforcing `validate_proof_bundle_summary_v1` schema/version, key/type stability, and deterministic PASS/FAIL/ERROR summary output.

## Preconditions
- `system/scripts/validate-proof-bundle.sh` exists on the branch tip and supports `--summary-json`.

## Files allowed to touch
- tests/test_validate_proof_bundle_summary_json_contract.sh
- system/scripts/validate-proof-bundle.sh
- docs/dev/evidence/TASK_177/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- system/scripts/release-gate.sh
- system/scripts/codex-unattended.sh
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- New deterministic contract test validates summary JSON schema/version and required keys/types on PASS, FAIL, and ERROR paths.
- Minimal validator edits only if required to satisfy explicit schema/taxonomy contract.
- Evidence transcript proves deterministic summary JSON digests across two runs per representative path.

## Deterministic test plan
1. Run validator with `--summary-json` on valid bundle twice and compare JSON SHA256.
2. Run controlled contract-failure case twice (exit `1`) and compare JSON SHA256.
3. Run controlled runtime-error case twice (exit `2`) and compare JSON SHA256.

## Evidence required
- docs/dev/evidence/TASK_177/TESTS.txt

## STOP conditions
- Stop if validator or `--summary-json` support is missing on the branch tip (dependencies not merged).
- Stop if required schema contract changes exceed minimal additive edits.
- Stop if implementation requires edits outside allowlist.

## Return format
1) Summary
2) Files changed
3) Summary JSON schema/taxonomy checks
4) Determinism digest proof
