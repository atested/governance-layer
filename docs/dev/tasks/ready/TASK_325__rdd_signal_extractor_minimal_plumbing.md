# TASK_325 — RDD: Signal extractor minimal structural-feedback plumbing

SPEC_EXPECTED: CODE

## Intent
Implement the bounded Phase 4 extractor seam by adding a minimal script that reads decision-chain records, extracts RDD `structural_signals` from `triage_decision` records, and writes a deterministic flat signal index artifact.

## Acceptance criteria
- A standalone extractor script exists and runs from repo root without server integration.
- Extractor reads decision-chain JSONL input and processes only `triage_decision` records.
- Extractor extracts each structural signal into a flat index entry containing at minimum:
  - `signal_id`
  - `deficiency_class`
  - `surface`
  - `description`
  - `case_ref`
- Extractor output is written to `out/rdd/signal-index.json`.
- Output ordering is deterministic for identical input.
- Extractor is idempotent: repeated runs with identical input produce byte-identical output.
- Extractor is extraction-only:
  - no analysis
  - no pattern detection
  - no proposals
  - no rule updates
- Existing verifier/evaluator behavior remains unchanged.

## Files allowed to touch
- `scripts/extract-rdd-signals.py` (new)
- `tests/fixtures/rdd_chain_phase4_*.jsonl` (new or updated bounded fixtures)
- `tests/run-chain-tests.sh` (only if minimally required to wire bounded Phase 4 regression invocation)
- `docs/dev/evidence/RDD_SIGNAL_EXTRACT__v1/TASK_325/**`

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
- `docs/dev/evidence/RDD_SIGNAL_EXTRACT__v1/TASK_325/TESTS.txt`
- `docs/dev/evidence/RDD_SIGNAL_EXTRACT__v1/TASK_325/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_SIGNAL_EXTRACT__v1/TASK_325/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_SIGNAL_EXTRACT__v1/TASK_325/HOTFILE_SCAN.txt`

## Determinism expectations
- For identical chain input, `out/rdd/signal-index.json` hash is identical across repeated runs.
- Extracted entry ordering is stable and deterministic.

## STOP rules
- STOP if bounded extraction requires doctrine/process/planning edits.
- STOP if extraction requires server/registry integration.
- STOP if required output contract cannot be produced without broad redesign.

## Constraints
- Phase 4 scope is minimal structural-feedback plumbing only.
- No feedback analysis or recommendation engine.
- No merge work.
