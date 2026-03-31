# TASK_326 — RDD: Signal extractor deterministic coverage

SPEC_EXPECTED: CODE

## Intent
Add bounded Phase 4 coverage that validates signal extraction correctness, backward safety, and deterministic/idempotent output behavior for the minimal extractor lane.

## Acceptance criteria
- Dedicated test script validates Phase 4 extraction matrix with explicit PASS/FAIL markers.
- Required positive case:
  - chain containing `triage_decision` with structural signals yields expected flattened index entries.
- Required negative/safety cases:
  - non-triage records do not produce signal entries
  - triage record without `structural_signals` does not crash and does not emit invalid entries
  - malformed/missing required signal fields fail closed with stable reason output
- Determinism/idempotency checks:
  - two extractor runs on identical input produce identical output hashes
  - repeated writes preserve identical `out/rdd/signal-index.json` bytes
- Test script exits non-zero on any failure and prints aggregate PASS/FAIL.

## Files allowed to touch
- `tests/test_rdd_signal_extract.sh` (new)
- `tests/fixtures/rdd_chain_phase4_*.jsonl` (new or updated bounded fixtures)
- `scripts/extract-rdd-signals.py`
- `tests/run-chain-tests.sh` (only if minimally required to include Phase 4 extraction regression invocation)
- `docs/dev/evidence/RDD_SIGNAL_EXTRACT__v1/TASK_326/**`

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
- `scripts/verify-chain.py`
- Everything else.

## Required evidence artifacts
- `docs/dev/evidence/RDD_SIGNAL_EXTRACT__v1/TASK_326/TESTS.txt`
- `docs/dev/evidence/RDD_SIGNAL_EXTRACT__v1/TASK_326/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_SIGNAL_EXTRACT__v1/TASK_326/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_SIGNAL_EXTRACT__v1/TASK_326/HOTFILE_SCAN.txt`

## Determinism expectations
- Test harness emits stable normalized output hashes across repeated runs under identical inputs.
- Idempotency check output markers are deterministic.

## STOP rules
- STOP if bounded coverage requires hot-file edits.
- STOP if coverage requires doctrine/server/registry/process changes.
- STOP if deterministic assertions cannot be produced within this bounded seam.

## Constraints
- Coverage stays within Phase 4 extraction seam.
- No Phase 5 or broader structural feedback framework work.
- No merge work.
