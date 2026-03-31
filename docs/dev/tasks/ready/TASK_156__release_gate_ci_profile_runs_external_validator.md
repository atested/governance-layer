# TASK_156__release_gate_ci_profile_runs_external_validator.md

TASK_ID: TASK_156
Title: [External usability next] release-gate ci profile runs external validator
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_156
Status: Ready
Dependencies: TASK_154, TASK_146
Bucket: External Usability Next

## Goal
When `GOV_PROFILE=ci`, run `bash system/scripts/validate-proof-bundle.sh <outdir>` after proof-bundle emission and fail closed if the external validator reports a contract violation.

## Preconditions
- `system/scripts/validate-proof-bundle.sh` exists on origin/main (from TASK_154).
- `system/scripts/release-gate.sh` emits proof-bundle outputs under `out/proof-bundles/<run-id>/`.

## Files allowed to touch
- system/scripts/release-gate.sh
- tests/test_release_gate_ci_runs_external_validator.sh
- docs/dev/evidence/TASK_156/**

## Files forbidden to touch
- system/scripts/validate-proof-bundle.sh
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- CI profile path runs the external validator on the emitted proof-bundle directory and fails closed on validator failure.
- Deterministic regression test proves validator invocation with stable digest across two runs.

## Deterministic test plan
1. Run `tests/test_release_gate_ci_runs_external_validator.sh` twice with fixed run-id/output base.
2. Assert stable markers proving validator executed in CI profile.
3. Compare transcript digest across runs.

## Evidence required
- docs/dev/evidence/TASK_156/TESTS.txt

## STOP conditions
- Stop if `system/scripts/validate-proof-bundle.sh` is not present on origin/main.
- Stop if changes would touch files outside the allowlist.
- Stop if dev profile semantics change.

## Return format
1) Summary
2) Files changed
3) CI validator behavior
4) Test command(s) and exit codes
