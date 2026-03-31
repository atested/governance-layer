# TASK_149__status_bundle_v1_optional_contract_sanity_test.md

TASK_ID: TASK_149
Title: [External CI correctness] status_bundle_v1 optional contract sanity test
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_149
Status: Ready
Dependencies: TASK_141
Bucket: External CI correctness

## Goal
Add a deterministic optional-contract sanity test for `status_bundle.json`: validate `status_bundle_v1` fields when present, but pass with an INFO marker if the file is absent (optional output).

## Non-goals
- Do not make `status_bundle.json` required.
- Do not change release-gate profile semantics.
- Do not change `status_bundle.json` schema beyond validation in tests.

## Preconditions
- `status_bundle.json` may be emitted by release-gate proof-bundle output.
- `status_bundle_version` and integer `strictness.value` are defined by current contract.

## Files allowed to touch
- tests/test_status_bundle_v1_optional_contract.sh
- docs/dev/evidence/TASK_149/**

## Files forbidden to touch
- system/scripts/release-gate.sh
- docs/EXTERNAL_CONTRACTS.md
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Test passes when `status_bundle.json` is absent with a deterministic INFO marker.
- Test validates schema/version/types/required keys when file is present.
- Deterministic output markers across repeated runs.

## Success criteria
- Produces a CODE diff (at least one non-evidence path changed).
- Updates `docs/dev/evidence/TASK_149/TESTS.txt` with commands and `[exit=...]` markers.
- Transcript demonstrates both “present” and “absent” paths with stable markers.

## Deterministic test plan
1. Present-case: run release-gate with fixed run-id, then validate `status_bundle.json`.
2. Absent-case: run validator against directory without `status_bundle.json` and assert INFO+PASS semantics.
3. For present-case, record digest equality across two runs if the validator emits a summary digest.
4. Record commands, outputs, and `[exit=...]` markers in evidence.

## Evidence required
- docs/dev/evidence/TASK_149/TESTS.txt
- Transcript must include `$ ...` command lines and `[exit=...]` markers

## STOP conditions
- If tests would require changing `status_bundle.json` schema or release-gate behavior, stop and split behavior changes into a separate task.
- If required changes fall outside allowlist, stop and request a minimal spec allowlist adjustment.

## Return format
1) Summary
2) Files changed
3) Present/absent optional-contract behavior
4) Test command(s) and exit codes
