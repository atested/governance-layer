# TASK_157__validate_proof_bundle_supports_deterministic_summary_json.md

TASK_ID: TASK_157
Title: [External usability next] validate-proof-bundle supports deterministic summary JSON output
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_157
Status: Ready
Dependencies: TASK_154
Bucket: External Usability Next

## Goal
Extend `system/scripts/validate-proof-bundle.sh` to optionally emit deterministic summary JSON (`validate_proof_bundle_summary_v1`) via `--summary-json <path>` (or env equivalent), without changing existing text output semantics.

## Preconditions
- `system/scripts/validate-proof-bundle.sh` exists on origin/main.
- Proof-bundle outputs can be generated locally for regression testing.

## Files allowed to touch
- system/scripts/validate-proof-bundle.sh
- tests/test_validate_proof_bundle_summary_json.sh
- docs/dev/evidence/TASK_157/**

## Files forbidden to touch
- system/scripts/release-gate.sh
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Optional `--summary-json` emits deterministic JSON with schema version `validate_proof_bundle_summary_v1`.
- Regression test proves summary JSON digest equality across two runs.

## Deterministic test plan
1. Run `tests/test_validate_proof_bundle_summary_json.sh` twice on the same bundle.
2. Assert summary JSON SHA256 equality and required keys/schema version.

## Evidence required
- docs/dev/evidence/TASK_157/TESTS.txt

## STOP conditions
- Stop if `validate-proof-bundle.sh` is absent on origin/main.
- Stop if changes require touching files outside the allowlist.
- Stop if JSON output would break existing validator exit code behavior.

## Return format
1) Summary
2) Files changed
3) Summary JSON schema and determinism proof
4) Test command(s) and exit codes
