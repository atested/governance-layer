# TASK_337 — RDD: Selector-mode source contract hardening

SPEC_EXPECTED: CODE

## Intent
Harden selector-mode source handling for bounded v1 triage invocation so selector mode remains request-bound, auditable, and fail-closed when source data is invalid.

## Acceptance criteria
- Triage invocation path enforces selector-mode source contract in bounded v1 flow:
  - request-bound selector mode (when present) is used deterministically.
  - invalid request-bound selector mode values fail closed with stable marker.
  - absence of request-bound selector mode remains backward-compatible via documented default behavior.
- Ambient selector-mode inputs cannot silently override request-bound selector mode in the bounded invocation path.
- Mode/source markering remains explicit and stable for auditability.
- No doctrine/process/planning edits. No server or registry integration.

## Files allowed to touch
- `scripts/rdd-pass-triage.sh`
- `scripts/triage-eval.py`
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/fixtures/rdd_phase10_selector_mode_*.json` (new or updated bounded fixtures)
- `docs/dev/evidence/RDD_PHASE10_SELECTOR_MODE_SOURCE__v1/TASK_337/**`

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
- `docs/dev/evidence/RDD_PHASE10_SELECTOR_MODE_SOURCE__v1/TASK_337/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE10_SELECTOR_MODE_SOURCE__v1/TASK_337/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE10_SELECTOR_MODE_SOURCE__v1/TASK_337/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE10_SELECTOR_MODE_SOURCE__v1/TASK_337/HOTFILE_SCAN.txt`

## Determinism expectations
- Selector-mode source resolution is deterministic for identical inputs.
- Fail-closed reason markers for invalid source values are deterministic and stable.

## STOP rules
- STOP if source-contract hardening requires doctrine/process/planning edits.
- STOP if bounded hardening requires server/registry integration.
- STOP if backward compatibility for absent selector mode cannot be preserved without broad redesign.

## Constraints
- Scope is bounded selector-mode source contract hardening only for the current v1 case class.
- No second case-class implementation.
- No merge work.
