# TASK_144__github_actions_ci_runs_release_gate_with_gov_profile_ci.md

TASK_ID: TASK_144
Title: [External usability] GitHub Actions CI runs release-gate with GOV_PROFILE=ci and uploads proof-bundle artifacts
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_144
Status: Ready
Dependencies: TASK_138
Bucket: External usability

## Goal
Update the GitHub Actions workflow to invoke `release-gate.sh` with `GOV_PROFILE=ci` (gating proof-packet behavior) and upload proof-bundle artifacts from `out/proof-bundles/**`.

## Non-goals
- Do not broaden scope beyond the task goal.
- Do not change release-gate semantics or proof-bundle file contents.
- Do not modify unrelated workflow/queue specs.

## Files allowed to touch
- .github/workflows/release-gate.yml
- docs/dev/evidence/TASK_144/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Success criteria
- Produces a CODE diff (at least one non-evidence path changed).
- Workflow explicitly runs `GOV_PROFILE=ci bash system/scripts/release-gate.sh`.
- Workflow uploads `out/proof-bundles/**` artifacts.
- Updates `docs/dev/evidence/TASK_144/TESTS.txt` with commands and `[exit=...]` markers.

## Deterministic test plan
1. Run grep-based checks against `.github/workflows/release-gate.yml`.
2. Assert the workflow includes `GOV_PROFILE=ci` in the release-gate invocation.
3. Assert the workflow uploads `out/proof-bundles/**`.
4. Record commands, outputs, and `[exit=...]` markers in evidence.

## Evidence required
- docs/dev/evidence/TASK_144/TESTS.txt
- Transcript must include `$ ...` command lines and `[exit=...]` markers

## STOP conditions
- If origin/main already contains the exact workflow invocation and artifact path behavior, stop and convert to reconcile/provenance closeout.
- If required changes fall outside the allowlist, stop and request a minimal spec allowlist adjustment.

## Return format
1) Summary
2) Files changed
3) Checks performed
4) Command(s) and exit codes
