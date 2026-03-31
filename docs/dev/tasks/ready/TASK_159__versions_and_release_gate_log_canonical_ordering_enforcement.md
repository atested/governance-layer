# TASK_159__versions_and_release_gate_log_canonical_ordering_enforcement.md

TASK_ID: TASK_159
Title: [External usability next] versions.txt and release_gate_log.txt canonical ordering enforcement
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_159
Status: Ready
Dependencies: TASK_143
Bucket: External Usability Next

## Goal
Ensure `release-gate.sh` emits `versions.txt` and `release_gate_log.txt` with deterministic canonical key ordering and no duplicate keys, with a regression test proving stable ordering across runs.

## Preconditions
- `release-gate.sh` emits `versions.txt` and `release_gate_log.txt`.
- TASK_143 sidecar format contract tests exist on origin/main.

## Files allowed to touch
- system/scripts/release-gate.sh
- tests/test_release_gate_versions_and_log_ordering.sh
- docs/dev/evidence/TASK_159/**

## Files forbidden to touch
- tests/test_release_gate_aux_file_formats.sh
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Emission order for keys in `versions.txt` and `release_gate_log.txt` is deterministic.
- Duplicate-key emission is prevented in the emitter path.
- Regression test proves stable ordering + digest equality across two runs.

## Deterministic test plan
1. Run `tests/test_release_gate_versions_and_log_ordering.sh`.
2. Assert canonical key order and no duplicate keys.
3. Compare digests across two runs.

## Evidence required
- docs/dev/evidence/TASK_159/TESTS.txt

## STOP conditions
- Stop if enforcing ordering would require touching files outside the allowlist.
- Stop if duplicate-key enforcement requires broad refactor beyond emitter-local logic.

## Return format
1) Summary
2) Files changed
3) Ordering/duplicate-key enforcement behavior
4) Test command(s) and exit codes
