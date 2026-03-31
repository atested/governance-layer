# TASK_142__core_contract_enforcement_tests_for_proof_packet_and_release_gate_outputs.md

TASK_ID: TASK_142
Title: [External usability] Core contract enforcement tests for proof-packet and release-gate outputs
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_142
Status: Ready
Dependencies: TASK_136, TASK_141
Bucket: External usability

## Goal
Add deterministic tests that enforce proof-packet and release-gate output contract versions/hashes (manifest version, verifier summary report_version, proof_packet.sha256 format+content match).

## Non-goals
- Do not broaden scope beyond the task goal.
- Do not weaken fail-closed behavior or determinism guarantees.
- Do not modify unrelated workflow/queue specs.

## Files allowed to touch
- system/scripts/release-gate.sh
- scripts/proof-packet.py
- tests/test_proof_packet_contract_enforcement.sh
- docs/dev/evidence/TASK_142/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Success criteria
- Produces a CODE diff (at least one non-evidence path changed).
- Updates `docs/dev/evidence/TASK_142/TESTS.txt` with commands and `[exit=...]` markers.
- Deterministic test output digest/equality checks pass across two runs.

## Deterministic test plan
1. Run the task-specific test runner twice with fixed RELEASE_GATE_RUN_ID values.
2. Assert stable PASS markers and digest equality for the contract-reporting output.
3. Record commands, outputs, and `[exit=...]` markers in evidence.

## Evidence required
- docs/dev/evidence/TASK_142/TESTS.txt
- Transcript must include `$ ...` command lines and `[exit=...]` markers

## STOP conditions
- If origin/main already contains the full tests/behavior, stop and convert to reconcile/provenance closeout.
- If required changes fall outside the allowlist, stop and request a minimal spec allowlist adjustment.

## Return format
1) Summary
2) Files changed
3) Determinism proof
4) Test command(s) and exit codes
