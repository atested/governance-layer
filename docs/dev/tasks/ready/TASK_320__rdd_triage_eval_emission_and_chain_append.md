# TASK_320 — RDD: Triage evaluator emission and chain append

SPEC_EXPECTED: CODE

## Intent
Implement `scripts/triage-eval.py` as a standalone evaluator for the existing Phase 1 FS_COPY dest-exists-no-overwrite UNDECIDED case class. The script must accept a Pass v0.2 UNDECIDED record and emit a v0.2 triage decision record with deterministic findings, governing condition, disposition, structural signal, and correct chain linkage.

## Acceptance criteria
- `scripts/triage-eval.py` accepts exactly one input: path to a Pass decision record JSON.
- Input validation is fail-closed:
  - rejects non-JSON input
  - rejects records without `record_type: "pass_decision"`
  - rejects records without `policy_decision: "UNDECIDED"`
  - rejects records missing `record_hash` or `process_id`
- Output record includes:
  - `record_version: "0.2"`
  - `record_type: "triage_decision"`
  - `originating_pass_hash` equal to input Pass `record_hash`
  - `process_id` equal to input Pass `process_id`
  - non-empty `findings`
  - `governing_condition`
  - non-empty `governing_rationale`
  - `disposition`
  - `structural_signals`
- Findings include:
  - F1: `rule_gap`, `basis: "deterministic"`, `structural_deficiency: true`, no `basis_detail`
  - F2: `insufficient_information`, `basis: "judgmental"`, non-empty `basis_detail`, `structural_deficiency: false`
- `governing_condition` is `F1`.
- `disposition.type` is `DEFER_STRUCTURAL_DEFICIENCY`, with non-empty `signal_ref` and `structural_change_needed`.
- `structural_signals` contains one signal entry linked to F1.
- Triage output is appended to chain with correct `prev_record_hash` reference.
- Triage record uses existing signing infrastructure and passes `scripts/verify-record.py`.
- No ALLOW/DENY/UNDECIDED decision type is emitted by triage disposition.

## Files allowed to touch
- `scripts/triage-eval.py` (new)
- `scripts/verify-record.py` (only if strictly required for bounded triage record-type acceptance)
- `tests/fixtures/rdd_triage_pass_undecided_input.json` (new or updated fixture)
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_320/**`

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
- Everything else.

## Required evidence artifacts
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_320/TESTS.txt`
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_320/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_320/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_320/HOTFILE_SCAN.txt`

## Determinism expectations
- Same input Pass record yields byte-stable triage semantic fields across runs (excluding allowed runtime wrappers like timestamps if present; normalization must be deterministic and documented).
- Chain-link fields (`originating_pass_hash`, `process_id`, `prev_record_hash`) are deterministic and reproducible.

## STOP rules
- STOP if triage emission requires edits to doctrine, planning, registry, or server surfaces.
- STOP if required triage schema cannot be emitted without broad evaluator redesign.
- STOP if forbidden files must be edited.

## Constraints
- Bounded to Phase 2 FS_COPY dest-exists case class only.
- No Phase 3 chain-verifier expansion.
- No Phase 4 signal-extractor implementation.
- No merge work.
