# TASK_349 — RDD: Selector-mode legacy dual-alias allowed-value contract hardening

SPEC_EXPECTED: CODE

## Intent
Tighten bounded v1 selector-mode source handling by hardening legacy dual-alias allowed-value semantics after basic value validation, so dual legacy alias strings outside the bounded allowed selector-mode set fail closed with a stable marker.

## Acceptance criteria
- Existing canonical selector-mode source contract behavior remains intact:
  - canonical + legacy alias combinations fail closed with existing source-conflict markers.
  - canonical absent + only one legacy alias fails closed with existing source-forbidden markers.
- Existing legacy dual-alias value-invalid behavior remains intact:
  - canonical absent + both legacy aliases present where either legacy value is non-string or empty fails closed with existing legacy-value-invalid marker.
- Existing legacy dual-alias equal/mismatch behavior remains intact for allowed mode values:
  - equal allowed legacy values -> existing dual-alias conflict marker.
  - mismatched allowed legacy values -> existing dual-alias mismatch marker.
- New bounded behavior:
  - canonical absent + both legacy aliases present where either legacy value is a non-empty string outside the bounded selector-mode allowlist fails closed with stable legacy-value-unsupported marker.
- Canonical-only requests remain deterministic and backward-compatible for allowed values (`compat_legacy_single_case`, `explicit`).
- No doctrine/process/planning edits. No server or registry integration.

## Files allowed to touch
- `scripts/rdd-pass-triage.sh`
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/fixtures/rdd_phase16_selector_mode_*.json` (new or updated bounded fixtures)
- `docs/dev/evidence/RDD_PHASE16_SELECTOR_MODE_LEGACY_ALIAS_ALLOWED_VALUE_CONTRACT__v1/TASK_349/**`

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
- `docs/dev/evidence/RDD_PHASE16_SELECTOR_MODE_LEGACY_ALIAS_ALLOWED_VALUE_CONTRACT__v1/TASK_349/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE16_SELECTOR_MODE_LEGACY_ALIAS_ALLOWED_VALUE_CONTRACT__v1/TASK_349/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE16_SELECTOR_MODE_LEGACY_ALIAS_ALLOWED_VALUE_CONTRACT__v1/TASK_349/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE16_SELECTOR_MODE_LEGACY_ALIAS_ALLOWED_VALUE_CONTRACT__v1/TASK_349/HOTFILE_SCAN.txt`

## Determinism expectations
- Canonical-only selector-mode resolution remains deterministic for identical inputs.
- Legacy dual-alias invalid/unsupported/conflict/mismatch markers are deterministic and stable.

## STOP rules
- STOP if legacy dual-alias allowed-value hardening requires doctrine/process/planning edits.
- STOP if bounded allowed-value hardening requires server/registry integration.
- STOP if allowed-value hardening cannot be implemented without broad selector-mode redesign.

## Constraints
- Scope is bounded selector-mode legacy dual-alias allowed-value contract hardening for the current v1 case class only.
- No second case-class implementation.
- No merge work.
