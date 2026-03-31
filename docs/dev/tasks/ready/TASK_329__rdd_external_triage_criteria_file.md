# TASK_329 — RDD: External triage classification criteria file

SPEC_EXPECTED: CODE

## Intent
Externalize bounded FS_COPY triage classification criteria from `triage-eval.py` into a deterministic data file so criteria updates can be audited without changing core triage control flow.

## Acceptance criteria
- A deterministic criteria data file is introduced for the bounded v1 FS_COPY dest-exists-no-overwrite triage case.
- `triage-eval.py` loads criteria from this file for classification fields currently hardcoded in Phase 2 behavior.
- Output semantics remain backward-compatible for current v1 case class:
  - findings IDs/types/basis values
  - governing_condition/governing_rationale shape
  - disposition type and structural signal references
- Missing/malformed criteria file fails closed with deterministic error output.
- No server integration, no registry changes, no doctrine/process/planning edits.

## Files allowed to touch
- `scripts/triage-eval.py`
- `scripts/attest/rdd_triage_criteria.v1.json` (new)
- `tests/fixtures/rdd_phase6_triage_criteria_*.json` (new or updated bounded fixtures)
- `tests/test_rdd_triage_eval.sh` (only if minimally required to preserve current bounded behavior)
- `tests/test_rdd_triage_criteria_file.sh` (new)
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_FILE__v1/TASK_329/**`

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
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_FILE__v1/TASK_329/TESTS.txt`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_FILE__v1/TASK_329/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_FILE__v1/TASK_329/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_FILE__v1/TASK_329/HOTFILE_SCAN.txt`

## Determinism expectations
- Given identical input and criteria file, triage output remains deterministic across repeated runs.
- Criteria-file failure paths emit stable deterministic reason markers.

## STOP rules
- STOP if criteria externalization requires doctrine/process/planning edits.
- STOP if bounded criteria loading requires server/registry integration.
- STOP if backward compatibility cannot be preserved without broad redesign.

## Constraints
- Scope is criteria-source refactor only for current bounded v1 case class.
- No second case-class implementation in this task.
- No merge work.
