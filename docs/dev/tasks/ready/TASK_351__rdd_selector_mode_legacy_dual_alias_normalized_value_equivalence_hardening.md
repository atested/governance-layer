# TASK_351 — RDD: Selector-mode legacy dual-alias normalized-value equivalence hardening

SPEC_EXPECTED: CODE

## Intent
Tighten bounded v1 selector-mode source handling by hardening legacy dual-alias normalized-value equivalence semantics after value-validity and allowed-value checks, so whitespace-only formatting differences in legacy dual aliases do not trigger false mismatch markers.

## Acceptance criteria
- Existing canonical selector-mode source contract behavior remains intact:
  - canonical + legacy alias combinations fail closed with existing source-conflict markers.
  - canonical absent + only one legacy alias fails closed with existing source-forbidden markers.
- Existing legacy dual-alias value-invalid behavior remains intact:
  - canonical absent + both legacy aliases present where either legacy value is non-string or empty fails closed with existing legacy-value-invalid marker.
- Existing legacy dual-alias value-unsupported behavior remains intact:
  - canonical absent + both legacy aliases where one or both values are unsupported non-empty strings fails closed with existing legacy-value-unsupported marker.
- New bounded behavior:
  - canonical absent + both legacy aliases present where normalized (trimmed) allowed values are equal fails closed with existing dual-alias conflict marker even if raw strings differ by leading/trailing whitespace.
  - canonical absent + both legacy aliases present where normalized allowed values differ fails closed with existing dual-alias mismatch marker.
- Canonical-only requests remain deterministic and backward-compatible for allowed values (`compat_legacy_single_case`, `explicit`).
- No doctrine/process/planning edits. No server or registry integration.

## Files allowed to touch
- `scripts/rdd-pass-triage.sh`
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/fixtures/rdd_phase17_selector_mode_*.json` (new or updated bounded fixtures)
- `docs/dev/evidence/RDD_PHASE17_SELECTOR_MODE_LEGACY_ALIAS_NORMALIZED_VALUE_EQUIVALENCE__v1/TASK_351/**`

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
- `docs/dev/evidence/RDD_PHASE17_SELECTOR_MODE_LEGACY_ALIAS_NORMALIZED_VALUE_EQUIVALENCE__v1/TASK_351/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE17_SELECTOR_MODE_LEGACY_ALIAS_NORMALIZED_VALUE_EQUIVALENCE__v1/TASK_351/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE17_SELECTOR_MODE_LEGACY_ALIAS_NORMALIZED_VALUE_EQUIVALENCE__v1/TASK_351/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE17_SELECTOR_MODE_LEGACY_ALIAS_NORMALIZED_VALUE_EQUIVALENCE__v1/TASK_351/HOTFILE_SCAN.txt`

## Determinism expectations
- Canonical-only selector-mode resolution remains deterministic for identical inputs.
- Legacy dual-alias invalid/unsupported/conflict/mismatch markers remain deterministic and stable.

## STOP rules
- STOP if normalized-value equivalence hardening requires doctrine/process/planning edits.
- STOP if bounded hardening requires server/registry integration.
- STOP if normalized-value equivalence hardening cannot be implemented without broad selector-mode redesign.

## Constraints
- Scope is bounded selector-mode legacy dual-alias normalized-value equivalence hardening for the current v1 case class only.
- No second case-class implementation.
- No merge work.
