# TASK_096__integrated_e2e_determinism_records_aggregate_has.md

TASK_ID: TASK_096
Title: Integrated E2E determinism: records aggregate hash path independent
Executor: CODEX
Branch: codex/TASK_096
Status: Ready
Dependencies: []

## Goal
Ensure the integrated E2E harness produces identical RECORDS_SHA across two runs when record JSON contents are identical, regardless of absolute paths.

## Non-goals
No crypto strength guarantees; only determinism. No UI work.

## Files allowed to touch
- docs/dev/evidence/TASK_096/**
- scripts/replay-record.py
- scripts/policy-eval.py
- scripts/verify-record.py
- scripts/verify-chain.py
- tests/**
## Files forbidden to touch
[]

## Procedure
1) Confirm current repo has no scripts/attest and no tests/test_integrated_e2e_full.sh (already evidenced).
2) Implement a deterministic RECORDS_SHA aggregate that is path-independent:
   a) Use existing per-record stable identifiers already produced by the system (prefer record_hash / canonical JSON SHA-256 as defined in docs/dev/EPIC_SIGNING.md).
   b) Aggregate MUST NOT incorporate absolute paths or filesystem metadata.
   c) Aggregation MUST be order-independent: sort inputs deterministically (e.g., by record_hash bytes) before hashing.
3) Surface the aggregate in an existing deterministic tool path:
   - Preferred: scripts/replay-record.py prints RECORDS_SHA for the replay bundle (or writes it into a deterministic report artifact).
4) Add/extend a deterministic test under tests/ that:
   - Runs the aggregate computation twice over the same fixed input set
   - Asserts identical RECORDS_SHA across runs.
5) Write evidence:
   - docs/dev/evidence/TASK_096/TESTS.txt must include the exact commands run and [exit=...] markers.
## Acceptance criteria


- A RECORDS_SHA aggregate is computed from stable record identifiers (record_hash or equivalent canonical hash) without incorporating absolute paths.
- The aggregate is order-independent and reproducible (sorting + canonical byte hashing).
- Running the new/updated test twice yields identical RECORDS_SHA output.
- replay/verify tooling produces the same RECORDS_SHA when inputs are unchanged.
## Evidence required


- docs/dev/evidence/TASK_096/TESTS.txt containing:
  - command lines ($ ...)
  - exit markers ([exit=...])
  - captured RECORDS_SHA outputs from two runs demonstrating equality
## Return format
Return:
- The exact files changed
- The RECORDS_SHA definition (inputs, sorting rule, hashing preimage)
- Test name + command to run it
- The two identical RECORDS_SHA values from evidence
