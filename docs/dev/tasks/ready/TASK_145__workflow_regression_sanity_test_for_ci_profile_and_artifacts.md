# TASK_145__workflow_regression_sanity_test_for_ci_profile_and_artifacts.md

TASK_ID: TASK_145
Title: [External usability] Deterministic regression sanity test for CI workflow (GOV_PROFILE=ci + artifact paths)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_145
Status: Ready
Dependencies: TASK_144
Bucket: External usability

## Goal
Add a deterministic local regression test that validates the GitHub Actions release-gate workflow contains required CI-profile and artifact-upload behavior.

## Non-goals
- Do not modify release-gate semantics.
- Do not broaden into full workflow execution.
- Do not modify unrelated workflow/queue specs.

## Files allowed to touch
- tests/test_github_actions_release_gate_ci_profile.sh
- docs/dev/evidence/TASK_145/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Success criteria
- Produces a CODE diff (at least one non-evidence path changed).
- Adds a deterministic test that checks for checkout, setup-python, `GOV_PROFILE=ci` release-gate invocation, and `out/proof-bundles/**` artifact upload.
- Test computes a stable SHA256 digest of the workflow file across two reads and asserts equality.
- Updates `docs/dev/evidence/TASK_145/TESTS.txt` with commands and `[exit=...]` markers.

## Deterministic test plan
1. Run the workflow sanity test twice against `.github/workflows/release-gate.yml`.
2. Assert required step/path markers are present.
3. Assert workflow SHA256 is identical across two reads.
4. Record commands, outputs, and `[exit=...]` markers in evidence.

## Evidence required
- docs/dev/evidence/TASK_145/TESTS.txt
- Transcript must include `$ ...` command lines and `[exit=...]` markers

## STOP conditions
- If origin/main already contains an equivalent deterministic regression test, stop and convert to reconcile/provenance closeout.
- If required changes fall outside the allowlist, stop and request a minimal spec allowlist adjustment.

## Return format
1) Summary
2) Files changed
3) Determinism proof
4) Command(s) and exit codes
