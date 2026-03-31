# TASK_181__proof_bundle_dir_scanner_contract_ordering_and_rejection_markers.md

TASK_ID: TASK_181
Title: [External validator hardening 2] Proof-bundle dir scanner contract ordering and rejection markers
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_181
Status: Ready
Dependencies: TASK_170
Bucket: External Usability Next
SPEC_EXPECTED: CODE

## Goal
Add deterministic contract tests for `tests/test_proof_bundle_dir_contract_scan.sh`, enforcing stable `DIR_FILE_LIST` ordering and stable rejection markers for malformed optional-file linkages.

## Preconditions
- `tests/test_proof_bundle_dir_contract_scan.sh` exists on the branch tip.

## Files allowed to touch
- tests/test_proof_bundle_dir_contract_scan_contract.sh
- docs/dev/evidence/TASK_181/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- system/scripts/release-gate.sh
- system/scripts/codex-unattended.sh
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Deterministic test verifies sorted `DIR_FILE_LIST` contract and stable rejection markers on malformed optional-file linkage.
- Two-run digest equality recorded for PASS and FAIL cases.

## Deterministic test plan
1. Invoke scanner self-harness (or equivalent temp fixture) twice and assert stable `DIR_FILE_LIST`.
2. Invoke malformed optional-file linkage case twice and assert stable FAIL marker and digest.

## Evidence required
- docs/dev/evidence/TASK_181/TESTS.txt

## STOP conditions
- Stop if stable contract checks require edits outside allowlist.
- Stop if scanner test missing on branch tip.

## Return format
1) Summary
2) Files changed
3) Ordering/rejection marker checks
4) Determinism digest proof

