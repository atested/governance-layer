# TASK_357 — RDD: Selector-mode canonical request value-contract precedence hardening

SPEC_EXPECTED: CODE

## Intent
Tighten bounded v1 selector-mode source handling by hardening canonical request selector-mode value-contract precedence, so invalid canonical request mode values fail closed with invalid markers before legacy-source conflict classification.

## Acceptance criteria
- Existing canonical selector-mode source contract behavior remains intact for valid canonical values:
  - canonical + legacy alias combinations fail closed with existing source-conflict markers when canonical request mode is valid.
  - canonical absent + only one legacy alias fails closed with existing source-forbidden markers.
- Existing legacy dual-alias value-invalid behavior remains intact:
  - canonical absent + both legacy aliases present where either legacy value is non-string or empty fails closed with existing legacy-value-invalid marker.
- Existing legacy dual-alias value-unsupported behavior remains intact:
  - canonical absent + both legacy aliases where one or both values are unsupported non-empty strings fails closed with existing legacy-value-unsupported marker.
- Existing canonical request case-normalization behavior remains intact:
  - canonical request mode values that normalize (trim + lowercase) to `compat_legacy_single_case` or `explicit` are accepted and applied.
  - canonical request mode values outside the bounded allowed set after normalization fail closed with existing invalid marker.
- New bounded behavior:
  - when canonical request selector mode is present but invalid (non-string, empty, or unsupported normalized value), fail closed with existing canonical invalid marker even if legacy selector-mode aliases are also present.
  - invalid canonical request mode must not be reclassified as source conflict.
- Default compatibility behavior remains unchanged when canonical selector mode is absent.
- No doctrine/process/planning edits. No server or registry integration.

## Files allowed to touch
- `scripts/rdd-pass-triage.sh`
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/fixtures/rdd_phase20_selector_mode_*.json` (new or updated bounded fixtures)
- `docs/dev/evidence/RDD_PHASE20_SELECTOR_MODE_CANONICAL_REQUEST_VALUE_CONTRACT_PRECEDENCE__v1/TASK_357/**`

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
- `docs/dev/evidence/RDD_PHASE20_SELECTOR_MODE_CANONICAL_REQUEST_VALUE_CONTRACT_PRECEDENCE__v1/TASK_357/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE20_SELECTOR_MODE_CANONICAL_REQUEST_VALUE_CONTRACT_PRECEDENCE__v1/TASK_357/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE20_SELECTOR_MODE_CANONICAL_REQUEST_VALUE_CONTRACT_PRECEDENCE__v1/TASK_357/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE20_SELECTOR_MODE_CANONICAL_REQUEST_VALUE_CONTRACT_PRECEDENCE__v1/TASK_357/HOTFILE_SCAN.txt`

## Determinism expectations
- Canonical selector-mode resolution remains deterministic for identical inputs.
- Legacy dual-alias invalid/unsupported/conflict/mismatch markers remain deterministic and stable.

## STOP rules
- STOP if canonical request value-contract precedence hardening requires doctrine/process/planning edits.
- STOP if bounded hardening requires server/registry integration.
- STOP if canonical request value-contract precedence hardening cannot be implemented without broad selector-mode redesign.

## Constraints
- Scope is bounded selector-mode canonical request value-contract precedence hardening for the current v1 case class only.
- No second case-class implementation.
- No merge work.
