# TASK_333 — RDD: Triage selector contract strictness

SPEC_EXPECTED: CODE

## Intent
Harden the Phase 7 selector seam by enforcing an explicit selector-map contract for triage criteria lookup, so selector behavior is auditable, deterministic, and not dependent on implicit legacy fallback shape inference.

## Acceptance criteria
- `triage-eval.py` enforces explicit selector contract for criteria routing:
  - requires deterministic selector-map presence for selector-driven lookup, or
  - requires an explicitly documented compatibility mode with deterministic markering.
- Unsupported selector cases fail closed with stable selector-specific reason marker output.
- Missing selector target key fails closed with stable selector-specific reason marker output.
- Selector-map schema violations (wrong type/non-string entries/empty mapping where unsupported) fail closed with stable reason marker output.
- Existing bounded v1 FS_COPY selector path remains backward-compatible in emitted triage semantics:
  - findings IDs/types/basis values
  - governing_condition/governing_rationale shape
  - disposition type and structural signal references
- No server integration, no registry changes, no doctrine/process/planning edits.

## Files allowed to touch
- `scripts/triage-eval.py`
- `scripts/attest/rdd_triage_criteria.v1.json`
- `tests/fixtures/rdd_phase8_triage_selector_contract_*.json` (new or updated bounded fixtures)
- `tests/test_rdd_triage_criteria_selector.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_CONTRACT__v1/TASK_333/**`

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
- `scripts/verify-chain.py`
- `scripts/replay-record.py`
- Everything else.

## Required evidence artifacts
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_CONTRACT__v1/TASK_333/TESTS.txt`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_CONTRACT__v1/TASK_333/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_CONTRACT__v1/TASK_333/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_CONTRACT__v1/TASK_333/HOTFILE_SCAN.txt`

## Determinism expectations
- Given identical input and criteria file, selector contract path and triage output are deterministic.
- Selector contract failure paths emit stable deterministic reason markers.

## STOP rules
- STOP if selector-contract hardening requires doctrine/process/planning edits.
- STOP if bounded contract enforcement requires server/registry integration.
- STOP if bounded compatibility cannot be preserved without broad redesign.

## Constraints
- Scope is selector-contract hardening only for the bounded v1 case class.
- No second case-class implementation in this task.
- No merge work.
