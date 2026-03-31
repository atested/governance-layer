# TASK_341 — RDD: Selector-mode source-conflict fail-closed

SPEC_EXPECTED: CODE

## Intent
Tighten bounded v1 selector-mode source contract by rejecting conflicting multi-source selector-mode declarations in the same request, rather than silently choosing one source.

## Acceptance criteria
- Triage invocation path continues to accept selector mode only from canonical request-bound source:
  - `intent.constraints.selector_mode`
- If canonical selector mode is present and any legacy alias is also present, fail closed with stable conflict markers:
  - canonical + `intent.rdd.selector_mode`
  - canonical + `intent.selector_mode`
  - canonical + both legacy aliases
- If legacy aliases are present and canonical is absent, existing fail-closed behavior remains in place.
- Canonical-only requests remain deterministic and backward-compatible for allowed values (`compat_legacy_single_case`, `explicit`).
- No doctrine/process/planning edits. No server or registry integration.

## Files allowed to touch
- `scripts/rdd-pass-triage.sh`
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/fixtures/rdd_phase12_selector_mode_*.json` (new or updated bounded fixtures)
- `docs/dev/evidence/RDD_PHASE12_SELECTOR_MODE_SOURCE_CONFLICT__v1/TASK_341/**`

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
- `docs/dev/evidence/RDD_PHASE12_SELECTOR_MODE_SOURCE_CONFLICT__v1/TASK_341/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE12_SELECTOR_MODE_SOURCE_CONFLICT__v1/TASK_341/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE12_SELECTOR_MODE_SOURCE_CONFLICT__v1/TASK_341/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE12_SELECTOR_MODE_SOURCE_CONFLICT__v1/TASK_341/HOTFILE_SCAN.txt`

## Determinism expectations
- Canonical-only selector-mode resolution remains deterministic for identical inputs.
- Source-conflict fail-closed markers are deterministic and stable.

## STOP rules
- STOP if source-conflict handling requires doctrine/process/planning edits.
- STOP if bounded source-conflict handling requires server/registry integration.
- STOP if conflict handling cannot be implemented without broad selector-mode redesign.

## Constraints
- Scope is bounded selector-mode source-conflict handling for the current v1 case class only.
- No second case-class implementation.
- No merge work.
