# TASK_166__minimal_distribution_manifest_what_to_ship.md

TASK_ID: TASK_166
Title: [External packaging] Minimal distribution manifest (what to ship)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_166
Status: Ready
Dependencies: none
Bucket: External Usability Next

## Goal
Add a concise `docs/DISTRIBUTION.md` manifest describing what to ship for external use (required docs/scripts/expected outputs) and explicitly what not to commit.

## Preconditions
- `docs/EXTERNAL_CONTRACTS.md` and `README.md` exist on origin/main.

## Files allowed to touch
- docs/DISTRIBUTION.md
- docs/dev/evidence/TASK_166/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/bootstrap-run.sh
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- `docs/DISTRIBUTION.md` includes required docs/scripts and expected proof-bundle outputs.
- Explicitly states `out/proof-bundles/**` is runtime output and not committed.
- Evidence confirms section headings and key file references exist.

## Deterministic test plan
1. Run `rg` checks against `docs/DISTRIBUTION.md`.
2. Optionally show a short excerpt of headings and required file bullets.

## Evidence required
- docs/dev/evidence/TASK_166/TESTS.txt

## STOP conditions
- Stop if canonical distribution-manifest path should be elsewhere (path mismatch on origin/main).
- Stop if changes spill outside the allowlist.

## Return format
1) Summary
2) Files changed
3) Distribution manifest sections added
4) Evidence command(s) and exit codes

