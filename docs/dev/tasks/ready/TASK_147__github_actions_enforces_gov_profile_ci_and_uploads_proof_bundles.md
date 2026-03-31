# TASK_147__github_actions_enforces_gov_profile_ci_and_uploads_proof_bundles.md

TASK_ID: TASK_147
Title: [External CI correctness] GitHub Actions enforces GOV_PROFILE=ci and uploads proof-bundle outputs
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_147
Status: Ready
Dependencies: TASK_144, TASK_145
Bucket: External CI correctness

## Goal
Ensure `.github/workflows/release-gate.yml` runs `release-gate.sh` with `GOV_PROFILE=ci` and uploads proof-bundle outputs (`out/proof-bundles/**`) and the release-gate stdout log deterministically.

## Non-goals
- Do not change release-gate semantics.
- Do not add unrelated CI jobs or matrix expansion.
- Do not modify proof-bundle file content contracts.

## Preconditions
- `.github/workflows/release-gate.yml` exists on origin/main.
- `tests/test_github_actions_release_gate_ci_profile.sh` exists (or will be updated by this task).

## Files allowed to touch
- .github/workflows/release-gate.yml
- tests/test_github_actions_release_gate_ci_profile.sh
- docs/dev/evidence/TASK_147/**

## Files forbidden to touch
- system/scripts/release-gate.sh
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Workflow invokes `release-gate.sh` with `GOV_PROFILE=ci`.
- Workflow uploads `out/proof-bundles/**` and `out/release_gate.stdout.log`.
- A deterministic local workflow sanity test validates these invariants.

## Success criteria
- Produces a CODE diff (at least one non-evidence path changed).
- Updates `docs/dev/evidence/TASK_147/TESTS.txt` with commands and `[exit=...]` markers.
- Transcript proves CI-profile invocation and artifact upload paths are present.
- Workflow digest determinism check passes across two reads.

## Deterministic test plan
1. Run `tests/test_github_actions_release_gate_ci_profile.sh` twice.
2. Assert required workflow markers and digest equality.
3. Record commands, outputs, and `[exit=...]` markers in evidence.

## Evidence required
- docs/dev/evidence/TASK_147/TESTS.txt
- Transcript must include `$ ...` command lines and `[exit=...]` markers

## STOP conditions
- If origin/main already contains the exact CI-profile invocation and artifact path behavior with equivalent test coverage, stop and convert to reconcile/provenance closeout.
- If required changes fall outside the allowlist, stop and request a minimal spec allowlist adjustment.

## Return format
1) Summary
2) Files changed
3) Workflow checks performed
4) Test command(s) and exit codes
