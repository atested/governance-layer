# TASK_324 — RDD: Chain verifier test coverage and backward-compat regression

SPEC_EXPECTED: CODE

## Intent
Add bounded test coverage for Phase 3 RDD chain-verifier rules and backward-compat behavior, ensuring new multi-record validation is enforced without regressing existing chain verification surfaces.

## Acceptance criteria
- New dedicated test script validates Phase 3 chain-rule matrix with explicit PASS/FAIL markers.
- Required positive case:
  - Pass UNDECIDED -> Triage DEFER_STRUCTURAL_DEFICIENCY ordered chain passes.
- Required negative cases:
  - triage appears before pass for same `process_id`
  - terminal appears before triage for same `process_id`
  - triage references non-UNDECIDED pass
  - pass contains forbidden backward-link fields
  - duplicate triage decision for same `process_id`
- Backward-compat regression:
  - existing non-RDD chain fixture still passes verifier.
- Test script exits non-zero on any failure and prints aggregate PASS/FAIL.
- Determinism check runs the matrix twice and verifies stable normalized output hashes.

## Files allowed to touch
- `tests/test_rdd_chain_verify.sh` (new)
- `tests/fixtures/rdd_chain_phase3_valid.jsonl` (new or updated)
- `tests/fixtures/rdd_chain_phase3_invalid_*.jsonl` (new or updated)
- `tests/run-chain-tests.sh` (only if minimally required to include Phase 3 regression invocation)
- `scripts/verify-chain.py`
- `docs/dev/evidence/RDD_CHAIN_VERIFY__v1/TASK_324/**`

## Files forbidden to touch
- `docs/dev/ASSIGNMENTS.md`
- `docs/dev/WORK_QUEUE.md`
- `docs/RESIDUAL_DISCRETION_DOCTRINE.md`
- `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`
- `capabilities/capability-registry.json`
- `mcp/server.py`
- `system/scripts/release-gate.sh`
- `system/scripts/validate-proof-bundle.sh`
- `system/scripts/codex-unattended.sh`
- `scripts/policy-eval.py`
- `scripts/triage-eval.py`
- Everything else.

## Required evidence artifacts
- `docs/dev/evidence/RDD_CHAIN_VERIFY__v1/TASK_324/TESTS.txt`
- `docs/dev/evidence/RDD_CHAIN_VERIFY__v1/TASK_324/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_CHAIN_VERIFY__v1/TASK_324/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_CHAIN_VERIFY__v1/TASK_324/HOTFILE_SCAN.txt`

## Determinism expectations
- Test script emits identical normalized output and deterministic hash values on repeated runs under identical inputs.

## STOP rules
- STOP if adequate coverage requires hot-file edits or non-bounded process changes.
- STOP if bounded matrix coverage cannot be achieved without doctrine/server/registry edits.
- STOP if forbidden files must be edited.

## Constraints
- Coverage stays within Phase 3 verifier seam.
- No Phase 4 signal extractor work.
- No merge work.
