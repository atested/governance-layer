# TASK_167__proof_bundle_validator_usage_docs_cli_and_exit_taxonomy.md

TASK_ID: TASK_167
Title: [External packaging] Proof-bundle validator usage docs (CLI + exit taxonomy)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_167
Status: Ready
Dependencies: TASK_154
Bucket: External Usability Next

## Goal
Document `system/scripts/validate-proof-bundle.sh` usage in `docs/EXTERNAL_CONTRACTS.md`, including CLI examples, optional `--summary-json`, and deterministic exit taxonomy (0/1/2).

## Preconditions
- `system/scripts/validate-proof-bundle.sh` exists on origin/main.
- `docs/EXTERNAL_CONTRACTS.md` exists on origin/main.

## Files allowed to touch
- docs/EXTERNAL_CONTRACTS.md
- docs/dev/evidence/TASK_167/**

## Files forbidden to touch
- system/scripts/validate-proof-bundle.sh
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- `docs/EXTERNAL_CONTRACTS.md` includes validator CLI examples and `--summary-json`.
- Exit taxonomy `0/1/2` is documented clearly and deterministically.
- Evidence confirms section presence and exact CLI strings.

## Deterministic test plan
1. Run `rg` checks for validator CLI examples and exit code taxonomy.
2. Optionally show the added section excerpt.

## Evidence required
- docs/dev/evidence/TASK_167/TESTS.txt

## STOP conditions
- Stop if `docs/EXTERNAL_CONTRACTS.md` no longer exists on origin/main.
- Stop if documenting validator behavior requires changing validator code.
- Stop if changes spill outside the allowlist.

## Return format
1) Summary
2) Files changed
3) Validator usage docs coverage
4) Evidence command(s) and exit codes

