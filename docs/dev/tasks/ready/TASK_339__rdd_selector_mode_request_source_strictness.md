# TASK_339 — RDD: Selector-mode request-source strictness

SPEC_EXPECTED: CODE

## Intent
Tighten bounded v1 selector-mode source contract so selector mode is accepted only from the canonical request-bound field and legacy source aliases fail closed with explicit reason markers.

## Acceptance criteria
- Triage invocation path accepts selector mode only from canonical request-bound source:
  - `intent.constraints.selector_mode`
- Legacy selector-mode aliases fail closed with stable markers:
  - `intent.rdd.selector_mode`
  - `intent.selector_mode`
- Valid canonical selector-mode values remain deterministic (`compat_legacy_single_case`, `explicit`).
- Ambient selector-mode input remains non-authoritative and cannot silently override request-bound canonical mode.
- No doctrine/process/planning edits. No server or registry integration.

## Files allowed to touch
- `scripts/rdd-pass-triage.sh`
- `scripts/triage-eval.py`
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/fixtures/rdd_phase11_selector_mode_*.json` (new or updated bounded fixtures)
- `docs/dev/evidence/RDD_PHASE11_SELECTOR_MODE_SOURCE_STRICTNESS__v1/TASK_339/**`

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
- `docs/dev/evidence/RDD_PHASE11_SELECTOR_MODE_SOURCE_STRICTNESS__v1/TASK_339/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE11_SELECTOR_MODE_SOURCE_STRICTNESS__v1/TASK_339/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE11_SELECTOR_MODE_SOURCE_STRICTNESS__v1/TASK_339/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE11_SELECTOR_MODE_SOURCE_STRICTNESS__v1/TASK_339/HOTFILE_SCAN.txt`

## Determinism expectations
- Canonical request-source selector-mode resolution remains deterministic for identical inputs.
- Legacy-source fail-closed markers are deterministic and stable.

## STOP rules
- STOP if request-source strictness requires doctrine/process/planning edits.
- STOP if bounded strictness requires server/registry integration.
- STOP if backward compatibility for canonical source usage cannot be preserved without broad redesign.

## Constraints
- Scope is bounded selector-mode request-source strictness only for the current v1 case class.
- No second case-class implementation.
- No merge work.
