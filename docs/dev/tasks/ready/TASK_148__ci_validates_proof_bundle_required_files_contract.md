# TASK_148__ci_validates_proof_bundle_required_files_contract.md

TASK_ID: TASK_148
Title: [External CI correctness] CI validates proof-bundle required-files contract
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_148
Status: Ready
Dependencies: TASK_136, TASK_142, TASK_143
Bucket: External CI correctness

## Goal
Add a deterministic test validating the proof-bundle required-files contract from `docs/EXTERNAL_CONTRACTS.md`, including `proof_packet.sha256` checksum correctness for `proof_packet.tar`.

## Non-goals
- Do not redefine required vs optional files (that is docs/contract work).
- Do not modify proof-packet or release-gate semantics unless strictly needed for deterministic run-id hooks already allowed.
- Do not parse optional files as contract requirements.

## Preconditions
- `system/scripts/release-gate.sh` emits proof-bundle outputs.
- Required files are documented in `docs/EXTERNAL_CONTRACTS.md`.

## Files allowed to touch
- tests/test_proof_bundle_contract_required_files.sh
- system/scripts/release-gate.sh
- docs/dev/evidence/TASK_148/**

## Files forbidden to touch
- docs/EXTERNAL_CONTRACTS.md
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Deterministic test validates required-file presence in emitted proof-bundle directory.
- Test validates `proof_packet.sha256` format and checksum match to `proof_packet.tar`.
- Evidence shows one PASS case and one deterministic failure/sanity case.

## Success criteria
- Produces a CODE diff (at least one non-evidence path changed).
- Updates `docs/dev/evidence/TASK_148/TESTS.txt` with commands and `[exit=...]` markers.
- Transcript includes PASS markers and at least one deterministic failure marker/sanity check.

## Deterministic test plan
1. Run release-gate with fixed run-id/output base and validate required files.
2. Compute/verify checksum from `proof_packet.sha256` against `proof_packet.tar`.
3. Negative control: point validator at an empty/partial directory and assert deterministic failure marker.
4. Record commands, outputs, and `[exit=...]` markers in evidence.

## Evidence required
- docs/dev/evidence/TASK_148/TESTS.txt
- Transcript must include `$ ...` command lines and `[exit=...]` markers

## STOP conditions
- If required changes fall outside allowlist, stop and request minimal spec adjustment.
- If contract wording in `docs/EXTERNAL_CONTRACTS.md` is ambiguous vs observed behavior, stop and open a docs/contract clarification task instead of guessing.

## Return format
1) Summary
2) Files changed
3) Required-file checks and checksum validation
4) Test command(s) and exit codes
