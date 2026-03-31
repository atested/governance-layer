# TASK_323 — RDD: Chain verifier multi-record process rules

SPEC_EXPECTED: CODE

## Intent
Extend `scripts/verify-chain.py` with bounded multi-record RDD process verification rules so chain validation can enforce the one-way flow and record linkage guarantees introduced by Phase 1 and Phase 2.

## Acceptance criteria
- `verify-chain.py` groups records by `process_id` and applies process-order validation for records carrying RDD `record_type`.
- For records with the same `process_id`, accepted order is:
  - `pass_decision` then `triage_decision` then `terminal_judgment`
- Chain verifier rejects:
  - `triage_decision` before `pass_decision`
  - `terminal_judgment` before `triage_decision`
  - duplicate `triage_decision` or duplicate `terminal_judgment` for a single `process_id`
- Chain verifier validates `originating_pass_hash` on `triage_decision`:
  - referenced pass record exists in chain
  - referenced pass record has `policy_decision: "UNDECIDED"`
- Chain verifier rejects any `pass_decision` that contains backward-link fields:
  - `originating_triage_hash`
  - `originating_terminal_hash`
- Existing v0.1/v0.2 non-RDD chains without multi-record flow still pass unchanged.
- Failures are deterministic and fail-closed.

## Files allowed to touch
- `scripts/verify-chain.py`
- `tests/fixtures/rdd_chain_phase3_valid.jsonl` (new or updated)
- `tests/fixtures/rdd_chain_phase3_invalid_*.jsonl` (new or updated bounded matrix fixtures)
- `docs/dev/evidence/RDD_CHAIN_VERIFY__v1/TASK_323/**`

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
- `docs/dev/evidence/RDD_CHAIN_VERIFY__v1/TASK_323/TESTS.txt`
- `docs/dev/evidence/RDD_CHAIN_VERIFY__v1/TASK_323/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_CHAIN_VERIFY__v1/TASK_323/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_CHAIN_VERIFY__v1/TASK_323/HOTFILE_SCAN.txt`

## Determinism expectations
- Given identical chain input file, verifier outcome and reason output are deterministic across repeated runs.
- Invalid-chain checks produce stable rejection reasons.

## STOP rules
- STOP if enforcing multi-record rules requires doctrine/process/planning edits.
- STOP if bounded verifier rules cannot be added without touching forbidden files.
- STOP if backward compatibility requires registry/server changes.

## Constraints
- Scope is verifier-only for Phase 3 rule enforcement.
- No triage evaluator behavior changes.
- No signal extraction implementation (Phase 4).
- No merge work.
