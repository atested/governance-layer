# TASK_146__ci_integrates_contract_enforcement_tests_into_release_gate.md

TASK_ID: TASK_146
Title: [External CI correctness] CI integrates contract enforcement tests into release-gate (ci profile)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_146
Status: Ready
Dependencies: TASK_142, TASK_143
Bucket: External CI correctness

## Goal
Ensure the CI profile pathway (`GOV_PROFILE=ci`) runs the proof-bundle contract enforcement checks from TASK_142 and TASK_143 deterministically as part of `release-gate.sh`, failing closed when those checks fail.

## Non-goals
- Do not change dev-profile informational defaults.
- Do not modify proof-packet payload semantics or schema versions.
- Do not broaden release-gate into full CI orchestration.

## Preconditions
- `system/scripts/release-gate.sh` supports `GOV_PROFILE=ci`.
- `tests/test_proof_packet_contract_enforcement.sh` and `tests/test_release_gate_aux_file_formats.sh` exist on origin/main.
- Proof-bundle outputs are already emitted by release-gate.

## Files allowed to touch
- system/scripts/release-gate.sh
- tests/test_proof_packet_contract_enforcement.sh
- tests/test_release_gate_aux_file_formats.sh
- docs/dev/evidence/TASK_146/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- .github/workflows/**
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- `GOV_PROFILE=ci` release-gate execution deterministically runs both contract tests.
- Contract test failures propagate as fail-closed nonzero exit in CI profile.
- Dev profile defaults remain non-gating unless explicitly overridden.
- Evidence transcript demonstrates both checks running under CI profile.

## Success criteria
- Produces a CODE diff (at least one non-evidence path changed).
- Updates `docs/dev/evidence/TASK_146/TESTS.txt` with commands and `[exit=...]` markers.
- Transcript proves CI profile executes both contract checks and records deterministic PASS/FAIL markers.

## Deterministic test plan
1. Run release-gate in `GOV_PROFILE=ci` with deterministic run-id/output base.
2. Assert transcript includes invocations/results for:
   - `tests/test_proof_packet_contract_enforcement.sh`
   - `tests/test_release_gate_aux_file_formats.sh`
3. (Optional negative control) simulate one failing check and assert fail-closed behavior with stable marker.
4. Record commands, outputs, and `[exit=...]` markers in evidence.

## Evidence required
- docs/dev/evidence/TASK_146/TESTS.txt
- Transcript must include `$ ...` command lines and `[exit=...]` markers

## STOP conditions
- If origin/main already executes both checks in CI profile with equivalent deterministic behavior, stop and convert to reconcile/provenance closeout.
- If required changes fall outside the allowlist, stop and request a minimal spec allowlist adjustment.
- If integrating checks would change dev profile semantics, stop and split that behavior change into a separate task.

## Return format
1) Summary
2) Files changed
3) CI-profile behavior change
4) Test command(s) and exit codes
