# TASK_170__proof_bundle_directory_contract_scanner_tests_only.md

TASK_ID: TASK_170
Title: [External packaging tranche 2] Proof-bundle directory contract scanner (tests-only)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_170
Status: Ready
Dependencies: TASK_136, TASK_141, TASK_160
Bucket: External Usability Next

## Goal
Add a deterministic proof-bundle directory scanner test that validates required files and optional file semantics (including queue_drift_scan.json and status_bundle.json) for a caller-provided PROOF_BUNDLE_DIR.

## Preconditions
- `PROOF_BUNDLE_DIR` environment variable points to an existing proof-bundle output directory.
- Release-gate proof-bundle contract docs exist on origin/main.

## Files allowed to touch
- tests/test_proof_bundle_dir_contract_scan.sh
- docs/dev/evidence/TASK_170/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- `tests/test_proof_bundle_dir_contract_scan.sh` validates required files and optional semantics with deterministic stdout ordering and stable exit taxonomy (0/1/2).
- Evidence transcript proves two-run stdout digest equality on the same `PROOF_BUNDLE_DIR`.

## Deterministic test plan
1. Export `PROOF_BUNDLE_DIR=<path>` and run `tests/test_proof_bundle_dir_contract_scan.sh`.
2. Assert required files exist and optional file semantics/linkages are validated when present.
3. Run twice and compare stdout digests for determinism.

## Evidence required
- docs/dev/evidence/TASK_170/TESTS.txt

## STOP conditions
- Stop if implementation needs edits to `release-gate.sh` or `validate-proof-bundle.sh` (outside allowlist).
- Stop if `PROOF_BUNDLE_DIR` is missing or unreadable in evidence runs (runtime error path is allowed for the script but not completion evidence).
- Stop if changes spill outside allowlist.

## Return format
1) Summary
2) Files changed
3) Exit taxonomy (0/1/2)
4) Test command(s) and exit codes
