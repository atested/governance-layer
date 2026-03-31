# TASK_335 — RDD: Selector-mode explicit wiring for triage invocation

SPEC_EXPECTED: CODE

## Intent
Wire explicit selector-contract mode into bounded triage invocation paths so selector-map strictness can be enabled deterministically in normal RDD triage execution without ad hoc environment handling.

## Acceptance criteria
- Bounded invocation wiring supports explicit selector mode for triage execution in the current v1 RDD path.
- Triage invocation path sets or propagates selector mode deterministically and audibly (no implicit ambient dependency).
- Existing bounded v1 selector behavior remains backward-compatible when explicit mode is not requested.
- Explicit mode path fails closed deterministically when selector-map requirements are not met.
- No server integration, no registry changes, no doctrine/process/planning edits.

## Files allowed to touch
- `scripts/rdd-pass-triage.sh`
- `scripts/triage-eval.py`
- `tests/fixtures/rdd_phase9_selector_mode_*.json` (new or updated bounded fixtures)
- `tests/test_rdd_triage_selector_mode.sh` (new)
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_MODE__v1/TASK_335/**`

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
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_MODE__v1/TASK_335/TESTS.txt`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_MODE__v1/TASK_335/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_MODE__v1/TASK_335/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_MODE__v1/TASK_335/HOTFILE_SCAN.txt`

## Determinism expectations
- Explicit-mode invocation behavior is deterministic for identical input/fixtures.
- Explicit-mode fail-closed markers are deterministic and stable.

## STOP rules
- STOP if explicit-mode wiring requires doctrine/process/planning edits.
- STOP if bounded wiring requires server/registry integration.
- STOP if bounded compatibility cannot be preserved without broad redesign.

## Constraints
- Scope is selector-mode invocation wiring only for the bounded v1 case class.
- No second case-class implementation in this task.
- No merge work.
