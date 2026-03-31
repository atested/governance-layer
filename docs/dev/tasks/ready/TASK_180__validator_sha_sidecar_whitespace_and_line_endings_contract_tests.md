# TASK_180__validator_sha_sidecar_whitespace_and_line_endings_contract_tests.md

TASK_ID: TASK_180
Title: [External validator hardening 2] SHA sidecar whitespace/line-ending parsing contract tests
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_180
Status: Ready
Dependencies: TASK_154
Bucket: External Usability Next
SPEC_EXPECTED: CODE

## Goal
Add deterministic tests that enforce the proof-bundle `proof_packet.sha256` sidecar parsing contract for whitespace and line-ending edge cases.

## Preconditions
- `system/scripts/validate-proof-bundle.sh` exists on the branch tip.

## Files allowed to touch
- tests/test_validate_proof_bundle_sha_sidecar_contract.sh
- docs/dev/evidence/TASK_180/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- system/scripts/release-gate.sh
- system/scripts/codex-unattended.sh
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Deterministic test validates acceptance/rejection of SHA sidecar formatting edge cases with stable markers and exit codes.
- Includes two-run digest equality for representative PASS and FAIL cases.

## Deterministic test plan
1. Synthesize a valid proof-bundle temp dir.
2. Validate accepted canonical SHA sidecar format twice and compare digests.
3. Validate rejected whitespace/line-ending variants twice each and compare digests.

## Evidence required
- docs/dev/evidence/TASK_180/TESTS.txt

## STOP conditions
- Stop if implementing coverage requires edits outside allowlist.
- Stop if validator missing on branch tip.

## Return format
1) Summary
2) Files changed
3) SHA sidecar parsing cases
4) Determinism digest proof

