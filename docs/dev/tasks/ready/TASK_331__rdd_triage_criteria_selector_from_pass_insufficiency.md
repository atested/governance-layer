# TASK_331 — RDD: Triage criteria selector from pass insufficiency

SPEC_EXPECTED: CODE

## Intent
Remove the remaining hardcoded triage criteria key by selecting the criteria case from bounded Pass `insufficiency` signals, so triage classification remains deterministic while making the criteria-file seam extensible without control-flow rewrites.

## Acceptance criteria
- `triage-eval.py` no longer uses a single hardcoded criteria selector constant for all inputs.
- Triage criteria selection is derived deterministically from Pass `insufficiency` fields for the current bounded v1 FS_COPY dest-exists-no-overwrite case class.
- For the current v1 case class, output semantics remain backward-compatible:
  - findings IDs/types/basis values
  - governing_condition/governing_rationale shape
  - disposition type and structural signal references
- Unknown or unsupported insufficiency combinations fail closed with deterministic reason marker output.
- Missing selector-mapped criteria entry fails closed with deterministic reason marker output.
- No server integration, no registry changes, no doctrine/process/planning edits.

## Files allowed to touch
- `scripts/triage-eval.py`
- `scripts/attest/rdd_triage_criteria.v1.json`
- `tests/fixtures/rdd_phase7_triage_criteria_selector_*.json` (new or updated bounded fixtures)
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (new)
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_SELECTOR__v1/TASK_331/**`

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
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_SELECTOR__v1/TASK_331/TESTS.txt`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_SELECTOR__v1/TASK_331/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_SELECTOR__v1/TASK_331/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_SELECTOR__v1/TASK_331/HOTFILE_SCAN.txt`

## Determinism expectations
- Given identical input and criteria file, selected criteria path and triage output are deterministic across repeated runs.
- Unsupported-selector and missing-selector-entry failure paths emit stable deterministic reason markers.

## STOP rules
- STOP if selector externalization requires doctrine/process/planning edits.
- STOP if bounded selector loading requires server/registry integration.
- STOP if backward compatibility cannot be preserved without broad redesign.

## Constraints
- Scope is criteria-selection refactor only for the bounded v1 case class.
- No second case-class implementation in this task.
- No merge work.
