# TASK_169__github_actions_artifact_completeness_test_wildcard_optionals.md

TASK_ID: TASK_169
Title: [External packaging] GitHub Actions artifact completeness test (wildcard optionals)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_169
Status: Ready
Dependencies: TASK_158
Bucket: External Usability Next

## Goal
Add a deterministic GitHub Actions workflow sanity test that proves artifact upload coverage includes required proof-bundle artifacts and wildcard coverage for optional artifacts (`queue_drift_scan.json`, validator summary JSON) without modifying the workflow YAML.

## Preconditions
- `.github/workflows/release-gate.yml` exists on origin/main.

## Files allowed to touch
- tests/test_github_actions_release_gate_artifacts_completeness.sh
- docs/dev/evidence/TASK_169/**

## Files forbidden to touch
- .github/workflows/release-gate.yml
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Deterministic test asserts workflow artifact upload path includes `out/proof-bundles/**` and `out/release_gate.stdout.log`.
- Test explicitly records wildcard implication for optional artifacts when present.
- Transcript includes two-run workflow digest equality and stdout digest equality.

## Deterministic test plan
1. Run `tests/test_github_actions_release_gate_artifacts_completeness.sh`.
2. Assert required workflow markers and artifact paths.
3. Assert wildcard implication markers for optional artifacts.
4. Compare workflow and stdout digests across two runs.

## Evidence required
- docs/dev/evidence/TASK_169/TESTS.txt

## STOP conditions
- Stop if workflow file path/name differs from `.github/workflows/release-gate.yml`.
- Stop if checks require modifying workflow YAML (out of scope for this task).
- Stop if changes spill outside the allowlist.

## Return format
1) Summary
2) Files changed
3) Workflow artifact completeness checks
4) Test command(s) and exit codes

