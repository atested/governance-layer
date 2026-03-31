# TASK_345 — RDD: Selector-mode legacy dual-alias mismatch fail-closed

SPEC_EXPECTED: CODE

## Intent
Tighten bounded v1 selector-mode source handling by distinguishing dual legacy-alias mismatch from generic dual-alias conflict, so conflicting legacy values fail closed with a stable mismatch marker.

## Acceptance criteria
- Triage invocation path continues to accept selector mode only from canonical request-bound source:
  - `intent.constraints.selector_mode`
- Existing canonical conflict handling remains intact:
  - canonical + `intent.rdd.selector_mode` fails closed
  - canonical + `intent.selector_mode` fails closed
  - canonical + both legacy aliases fails closed
- Existing legacy single-alias fail-closed behavior remains intact:
  - canonical absent + only `intent.rdd.selector_mode` fails closed
  - canonical absent + only `intent.selector_mode` fails closed
- New bounded behavior for canonical absent + both legacy aliases:
  - if the two legacy alias values are equal, fail closed with existing dual-alias conflict marker.
  - if the two legacy alias values differ, fail closed with a stable legacy-alias-mismatch marker.
- Canonical-only requests remain deterministic and backward-compatible for allowed values (`compat_legacy_single_case`, `explicit`).
- No doctrine/process/planning edits. No server or registry integration.

## Files allowed to touch
- `scripts/rdd-pass-triage.sh`
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/fixtures/rdd_phase14_selector_mode_*.json` (new or updated bounded fixtures)
- `docs/dev/evidence/RDD_PHASE14_SELECTOR_MODE_LEGACY_ALIAS_MISMATCH__v1/TASK_345/**`

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
- `docs/dev/evidence/RDD_PHASE14_SELECTOR_MODE_LEGACY_ALIAS_MISMATCH__v1/TASK_345/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE14_SELECTOR_MODE_LEGACY_ALIAS_MISMATCH__v1/TASK_345/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE14_SELECTOR_MODE_LEGACY_ALIAS_MISMATCH__v1/TASK_345/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE14_SELECTOR_MODE_LEGACY_ALIAS_MISMATCH__v1/TASK_345/HOTFILE_SCAN.txt`

## Determinism expectations
- Canonical-only selector-mode resolution remains deterministic for identical inputs.
- Legacy dual-alias mismatch and dual-alias conflict markers are deterministic and stable.

## STOP rules
- STOP if legacy dual-alias mismatch handling requires doctrine/process/planning edits.
- STOP if bounded mismatch handling requires server/registry integration.
- STOP if mismatch handling cannot be implemented without broad selector-mode redesign.

## Constraints
- Scope is bounded selector-mode legacy dual-alias mismatch handling for the current v1 case class only.
- No second case-class implementation.
- No merge work.
