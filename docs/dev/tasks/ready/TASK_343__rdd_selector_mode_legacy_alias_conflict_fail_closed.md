# TASK_343 — RDD: Selector-mode legacy-alias conflict fail-closed

SPEC_EXPECTED: CODE

## Intent
Tighten bounded v1 selector-mode source handling by rejecting legacy-only multi-alias selector-mode declarations as an explicit source conflict, rather than emitting a single-source-forbidden marker.

## Acceptance criteria
- Triage invocation path continues to accept selector mode only from canonical request-bound source:
  - `intent.constraints.selector_mode`
- Existing canonical conflict handling remains intact:
  - canonical + `intent.rdd.selector_mode` fails closed
  - canonical + `intent.selector_mode` fails closed
  - canonical + both legacy aliases fails closed
- New bounded behavior:
  - canonical absent + both legacy aliases present (`intent.rdd.selector_mode` and `intent.selector_mode`) fails closed with a stable legacy-conflict marker.
- Existing legacy single-alias fail-closed behavior remains intact:
  - canonical absent + only `intent.rdd.selector_mode` fails closed with stable marker.
  - canonical absent + only `intent.selector_mode` fails closed with stable marker.
- Canonical-only requests remain deterministic and backward-compatible for allowed values (`compat_legacy_single_case`, `explicit`).
- No doctrine/process/planning edits. No server or registry integration.

## Files allowed to touch
- `scripts/rdd-pass-triage.sh`
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/fixtures/rdd_phase13_selector_mode_*.json` (new or updated bounded fixtures)
- `docs/dev/evidence/RDD_PHASE13_SELECTOR_MODE_LEGACY_ALIAS_CONFLICT__v1/TASK_343/**`

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
- `docs/dev/evidence/RDD_PHASE13_SELECTOR_MODE_LEGACY_ALIAS_CONFLICT__v1/TASK_343/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE13_SELECTOR_MODE_LEGACY_ALIAS_CONFLICT__v1/TASK_343/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE13_SELECTOR_MODE_LEGACY_ALIAS_CONFLICT__v1/TASK_343/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE13_SELECTOR_MODE_LEGACY_ALIAS_CONFLICT__v1/TASK_343/HOTFILE_SCAN.txt`

## Determinism expectations
- Canonical-only selector-mode resolution remains deterministic for identical inputs.
- Legacy-alias conflict fail-closed markers are deterministic and stable.

## STOP rules
- STOP if legacy-alias conflict handling requires doctrine/process/planning edits.
- STOP if bounded legacy-alias conflict handling requires server/registry integration.
- STOP if conflict handling cannot be implemented without broad selector-mode redesign.

## Constraints
- Scope is bounded selector-mode legacy-alias conflict handling for the current v1 case class only.
- No second case-class implementation.
- No merge work.
