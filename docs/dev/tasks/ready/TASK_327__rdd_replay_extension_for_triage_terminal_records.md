# TASK_327 — RDD: Replay extension for triage and terminal record types

SPEC_EXPECTED: CODE

## Intent
Extend `scripts/replay-record.py` with bounded RDD support for replay checks on `triage_decision` and `terminal_judgment` records so post-Phase-4 chains can be audited without forcing policy-eval re-execution for non-pass record types.

## Acceptance criteria
- `replay-record.py` supports a type-aware replay path for records with `record_type` equal to:
  - `triage_decision`
  - `terminal_judgment`
- For supported non-pass record types, replay checks are bounded to deterministic integrity invariants and must not invoke policy-eval.
- Required deterministic integrity checks for triage/terminal records include at minimum:
  - `record_type` and `process_id` presence/shape validation
  - required originating-link field presence for the specific type
  - canonical signed-payload/hash/signature verification via existing verifier surface
  - deterministic mismatch reporting with stable reason markers
- Existing pass-decision replay behavior remains backward-compatible.
- Unsupported/non-replayable record categories fail closed with explicit deterministic error output.

## Files allowed to touch
- `scripts/replay-record.py`
- `tests/fixtures/rdd_phase5_replay_*.json` (new or updated bounded fixtures)
- `tests/test_replay_rdd_phase5.sh` (new)
- `tests/test_replay.sh` (only if minimally required to wire bounded Phase 5 regression invocation)
- `docs/dev/evidence/RDD_REPLAY_EXTENSION__v1/TASK_327/**`

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
- `scripts/triage-eval.py`
- `scripts/verify-chain.py`
- Everything else.

## Required evidence artifacts
- `docs/dev/evidence/RDD_REPLAY_EXTENSION__v1/TASK_327/TESTS.txt`
- `docs/dev/evidence/RDD_REPLAY_EXTENSION__v1/TASK_327/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_REPLAY_EXTENSION__v1/TASK_327/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_REPLAY_EXTENSION__v1/TASK_327/HOTFILE_SCAN.txt`

## Determinism expectations
- Given identical input records, replay output and mismatch markers are deterministic across repeated runs.
- Expected-failure paths produce stable reason output.

## STOP rules
- STOP if replay extension requires doctrine/process/planning edits.
- STOP if bounded support for triage/terminal replay requires server/registry integration.
- STOP if required checks cannot be implemented without broad replay architecture redesign.

## Constraints
- Scope is replay-verifier extension only for RDD triage/terminal compatibility.
- No evaluator behavior changes.
- No merge work.
