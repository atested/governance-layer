# TASK_321 — RDD: Pass to Triage conditional invocation wiring

SPEC_EXPECTED: CODE

## Intent
Add bounded invocation wiring so triage runs only when Pass emits `policy_decision: "UNDECIDED"` for the existing FS_COPY dest-exists-no-overwrite case class. Preserve fail-closed behavior and keep wiring outside server/registry surfaces.

## Acceptance criteria
- A single bounded caller path exists for Pass→Triage flow using existing script-style interfaces.
- Caller runs `policy-eval.py` first and inspects the emitted Pass record.
- Caller invokes `triage-eval.py` if and only if Pass `policy_decision` equals `"UNDECIDED"`.
- Non-UNDECIDED Pass results do not invoke triage.
- UNDECIDED flow appends a triage record to the same chain file/location with correct linkage.
- Invocation returns non-zero on malformed input, missing files, or triage execution failure.
- Wiring does not change ALLOW/DENY semantics for non-UNDECIDED flows.
- Wiring remains deterministic for identical inputs and filesystem state.

## Files allowed to touch
- `scripts/rdd-pass-triage.sh` (new)
- `scripts/triage-eval.py`
- `tests/fixtures/fs_copy_dest_exists_undecided.json` (only if path contract refinement is needed for portable invocation)
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_321/**`

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
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_321/TESTS.txt`
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_321/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_321/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_321/HOTFILE_SCAN.txt`

## Determinism expectations
- For identical input and filesystem state:
  - invocation decision (invoke triage or not) is stable
  - produced records and chain links are stable after deterministic normalization.

## STOP rules
- STOP if conditional wiring requires server integration or registry edits.
- STOP if wiring cannot be added without touching protected hot files.
- STOP if forbidden files must be edited.

## Constraints
- No doctrine rewrite.
- No cross-surface architectural expansion.
- No merge work.
