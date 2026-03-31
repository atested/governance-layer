# TASK_353 — RDD: Selector-mode legacy dual-alias case-normalization hardening

SPEC_EXPECTED: CODE

## Intent
Tighten bounded v1 selector-mode source handling by hardening legacy dual-alias case-normalization semantics after trimmed-value normalization and allowed-value checks, so case-only formatting differences in allowed legacy dual-alias values do not trigger false mismatch markers.

## Acceptance criteria
- Existing canonical selector-mode source contract behavior remains intact:
  - canonical + legacy alias combinations fail closed with existing source-conflict markers.
  - canonical absent + only one legacy alias fails closed with existing source-forbidden markers.
- Existing legacy dual-alias value-invalid behavior remains intact:
  - canonical absent + both legacy aliases present where either legacy value is non-string or empty fails closed with existing legacy-value-invalid marker.
- Existing legacy dual-alias value-unsupported behavior remains intact:
  - canonical absent + both legacy aliases where one or both values are unsupported non-empty strings fails closed with existing legacy-value-unsupported marker.
- Existing normalized-whitespace behavior remains intact:
  - canonical absent + both legacy aliases with equal trimmed allowed values fails closed with existing dual-alias conflict marker.
  - canonical absent + both legacy aliases with different trimmed allowed values fails closed with existing dual-alias mismatch marker.
- New bounded behavior:
  - canonical absent + both legacy aliases present where trimmed allowed values are equal after lowercase normalization fails closed with existing dual-alias conflict marker even when legacy aliases differ only by case.
  - canonical absent + both legacy aliases present where trimmed allowed values differ after lowercase normalization fails closed with existing dual-alias mismatch marker.
- Canonical-only requests remain deterministic and backward-compatible for allowed values (`compat_legacy_single_case`, `explicit`).
- No doctrine/process/planning edits. No server or registry integration.

## Files allowed to touch
- `scripts/rdd-pass-triage.sh`
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/fixtures/rdd_phase18_selector_mode_*.json` (new or updated bounded fixtures)
- `docs/dev/evidence/RDD_PHASE18_SELECTOR_MODE_LEGACY_ALIAS_CASE_NORMALIZATION__v1/TASK_353/**`

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
- `docs/dev/evidence/RDD_PHASE18_SELECTOR_MODE_LEGACY_ALIAS_CASE_NORMALIZATION__v1/TASK_353/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE18_SELECTOR_MODE_LEGACY_ALIAS_CASE_NORMALIZATION__v1/TASK_353/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE18_SELECTOR_MODE_LEGACY_ALIAS_CASE_NORMALIZATION__v1/TASK_353/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE18_SELECTOR_MODE_LEGACY_ALIAS_CASE_NORMALIZATION__v1/TASK_353/HOTFILE_SCAN.txt`

## Determinism expectations
- Canonical-only selector-mode resolution remains deterministic for identical inputs.
- Legacy dual-alias invalid/unsupported/conflict/mismatch markers remain deterministic and stable.

## STOP rules
- STOP if case-normalization hardening requires doctrine/process/planning edits.
- STOP if bounded hardening requires server/registry integration.
- STOP if case-normalization hardening cannot be implemented without broad selector-mode redesign.

## Constraints
- Scope is bounded selector-mode legacy dual-alias case-normalization hardening for the current v1 case class only.
- No second case-class implementation.
- No merge work.
