# TASK_311 — RDD: Pass record v0.2 schema fields

SPEC_EXPECTED: CODE

## Intent

Extend `scripts/policy-eval.py` to emit three new fields on every decision record: `record_version: "0.2"`, `record_type: "pass_decision"`, and `process_id`. These are additive changes — no existing ALLOW/DENY behavior changes. This is the schema infrastructure required before UNDECIDED emission (TASK_312).

`process_id` is computed deterministically as: `sha256(session_id + ":" + request_id + ":process")`, taking the first 16 hex characters of the result.

## Acceptance criteria

- All emitted records include `"record_version": "0.2"` (was `"0.1"`)
- All emitted records include `"record_type": "pass_decision"`
- All emitted records include `"process_id"` — a 16-character hex string
- `process_id` is deterministic: same `session_id` + `request_id` inputs always produce the same `process_id`
- All existing ALLOW cases continue to produce `"policy_decision": "ALLOW"` unchanged
- All existing DENY cases continue to produce `"policy_decision": "DENY"` unchanged
- All existing reason codes, field values, and chain semantics are unaffected
- Existing test suite passes (update any tests that assert `"record_version": "0.1"` to assert `"0.2"`)

## Files allowed to touch

- `scripts/policy-eval.py`
- `tests/test_*.sh` — only to update `"record_version": "0.1"` assertions to `"0.2"` where they exist; no other test logic changes
- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_311/**`

## Files forbidden to touch

- `docs/dev/ASSIGNMENTS.md`
- `docs/dev/WORK_QUEUE.md`
- `capabilities/capability-registry.json`
- `mcp/server.py`
- `system/scripts/release-gate.sh`
- `system/scripts/validate-proof-bundle.sh`
- `system/scripts/codex-unattended.sh`
- `tests/fixtures/**` — no fixture changes in this task
- Everything else.

## Required evidence artifacts

- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_311/TESTS.txt` — full test suite output showing all tests pass
- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_311/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_311/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_311/HOTFILE_SCAN.txt`

## Determinism expectations

- `process_id` is deterministic for a given `session_id` + `request_id` pair
- All other record fields remain deterministic as before

## STOP rules

- STOP if `record_version` change breaks more than 5 test files (indicates broader impact than expected; report as a blocker)
- STOP if adding `record_type` or `process_id` changes any ALLOW/DENY outcome
- STOP if `process_id` generation requires any dependency not already available in `policy-eval.py`
- STOP if forbidden files must be edited

## Constraints

- Additive changes only. No behavioral change.
- Do not implement UNDECIDED emission — that is TASK_312.
- Do not add the `insufficiency` field — that is TASK_312.
- `record_type` is always `"pass_decision"` in this task; other record types (triage_decision, terminal_judgment) are out of scope.
