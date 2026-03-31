# TASK_171__docs_consistency_check_for_required_optional_proof_bundle_outputs.md

TASK_ID: TASK_171
Title: [External packaging tranche 2] Docs consistency check for required/optional proof-bundle outputs
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_171
Status: Ready
Dependencies: TASK_166, TASK_167
Bucket: External Usability Next

## Goal
Add a deterministic docs consistency test for proof-bundle required/optional output references across README, EXTERNAL_CONTRACTS, and DISTRIBUTION docs.

## Preconditions
- `README.md`, `docs/EXTERNAL_CONTRACTS.md`, and `docs/DISTRIBUTION.md` exist on origin/main.

## Files allowed to touch
- tests/test_external_docs_contract_consistency.sh
- docs/dev/evidence/TASK_171/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Deterministic test verifies required/optional file references are present in the expected docs.
- Evidence transcript proves two-run stdout digest equality.

## Deterministic test plan
1. Run `tests/test_external_docs_contract_consistency.sh`.
2. Assert required files appear in README/EXTERNAL_CONTRACTS and DISTRIBUTION, and optional files appear in EXTERNAL_CONTRACTS and DISTRIBUTION.
3. Run twice and compare stdout digests.

## Evidence required
- docs/dev/evidence/TASK_171/TESTS.txt

## STOP conditions
- Stop if task requires editing docs (outside allowlist for this task).
- Stop if changes spill outside allowlist.

## Return format
1) Summary
2) Files changed
3) Consistency checks enforced
4) Test command(s) and exit codes
