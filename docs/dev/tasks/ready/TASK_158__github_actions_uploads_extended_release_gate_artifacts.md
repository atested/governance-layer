# TASK_158__github_actions_uploads_extended_release_gate_artifacts.md

TASK_ID: TASK_158
Title: [External usability next] GitHub Actions uploads extended release-gate artifacts
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_158
Status: Ready
Dependencies: TASK_147, TASK_157
Bucket: External Usability Next

## Goal
Update GitHub Actions release-gate workflow artifact handling to explicitly cover extended outputs (including validator summary JSON when present) while preserving existing proof-bundle upload paths.

## Preconditions
- `.github/workflows/release-gate.yml` exists on origin/main.
- Workflow already uploads `out/proof-bundles/**` and `out/release_gate.stdout.log`.

## Files allowed to touch
- .github/workflows/release-gate.yml
- tests/test_github_actions_release_gate_artifacts_extended.sh
- docs/dev/evidence/TASK_158/**

## Files forbidden to touch
- system/scripts/**
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Workflow/test explicitly validate extended artifact coverage expectations.
- Deterministic workflow sanity test proves required paths and digest stability.

## Deterministic test plan
1. Run `tests/test_github_actions_release_gate_artifacts_extended.sh`.
2. Assert required workflow steps/paths and extended artifact path expectations.
3. Assert digest equality across two reads.

## Evidence required
- docs/dev/evidence/TASK_158/TESTS.txt

## STOP conditions
- Stop if workflow path/name differs on origin/main and requires a spec change.
- Stop if changes spill outside allowlist.

## Return format
1) Summary
2) Files changed
3) Workflow artifact coverage behavior
4) Test command(s) and exit codes
