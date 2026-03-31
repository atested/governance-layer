# TASK_151__external_ci_single_command_smoke_bootstrap_release_gate.md

TASK_ID: TASK_151
Title: [External CI correctness] External CI single-command smoke (bootstrap + release-gate + contract checks)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_151
Status: Ready
Dependencies: TASK_135, TASK_136, TASK_141, TASK_142, TASK_143
Bucket: External CI correctness

## Goal
Define and implement a deterministic end-to-end external CI smoke test that runs the bootstrap runner + release-gate and validates core proof-bundle contract outputs and summary version markers.

## Non-goals
- Do not add full integration/performance coverage.
- Do not modify proof-packet semantics or release-gate profile semantics beyond what is needed for deterministic smoke execution.
- Do not replace existing focused contract/unit tests.

## Preconditions
- `system/scripts/bootstrap-run.sh` exists and supports a non-destructive/dry-run or deterministic execution path.
- `system/scripts/release-gate.sh` emits proof-bundle outputs including summary JSON.
- Core contract enforcement tests exist or are implemented by dependent tasks.

## Files allowed to touch
- system/scripts/bootstrap-run.sh
- system/scripts/release-gate.sh
- tests/test_external_ci_smoke.sh
- docs/dev/evidence/TASK_151/**

## Files forbidden to touch
- .github/workflows/**
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Test runs bootstrap + release-gate in a deterministic local CI-like flow.
- Asserts proof-bundle required files exist.
- Asserts verifier summary `report_version == proof_packet_verify_summary_v1`.
- Emits deterministic digest/equality proof across two runs.

## Success criteria
- Produces a CODE diff (at least one non-evidence path changed).
- Updates `docs/dev/evidence/TASK_151/TESTS.txt` with commands and `[exit=...]` markers.
- Transcript includes deterministic digests and PASS markers for contract checks.

## Deterministic test plan
1. Run bootstrap + release-gate flow twice with fixed run-ids/output bases (or deterministic override).
2. Assert required proof-bundle files exist.
3. Assert proof-packet verify summary `report_version == proof_packet_verify_summary_v1`.
4. Compute/compare deterministic digests for primary outputs.
5. Record commands, outputs, and `[exit=...]` markers in evidence.

## Evidence required
- docs/dev/evidence/TASK_151/TESTS.txt
- Transcript must include `$ ...` command lines and `[exit=...]` markers

## STOP conditions
- If bootstrap-run lacks a safe deterministic mode and adding one would exceed scope, stop and split prerequisites into a smaller task.
- If required changes fall outside allowlist, stop and request a minimal spec allowlist adjustment.
- If the flow is nondeterministic across two runs, stop with a minimal repro before widening scope.

## Return format
1) Summary
2) Files changed
3) Determinism proof
4) Test command(s) and exit codes
