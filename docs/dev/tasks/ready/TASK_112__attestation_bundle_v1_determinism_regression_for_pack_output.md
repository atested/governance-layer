# TASK_112__attestation_bundle_v1_determinism_regression_for_pack_output.md

TASK_ID: TASK_112
Title: Attestation bundle v1: determinism regression for pack output
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_112
Status: Ready
Dependencies: TASK_110
Bucket: Attestation bundle v1

## Goal
Add a deterministic regression test that proves attestation bundle pack output is byte-stable across repeated runs.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- scripts/attest/bundle.py
- tests/test_attestation_bundle_determinism.sh
- tests/fixtures/attestation_bundle/**
- docs/dev/evidence/TASK_112/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_112/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- `tests/test_attestation_bundle_determinism.sh` runs pack twice and asserts identical manifest hash and file list ordering.
- Evidence records both hashes and exits 0.
- No non-deterministic fields remain in the packed manifest output.

## Deterministic test plan (commands)
- `bash tests/test_attestation_bundle_determinism.sh`

## Evidence required
- `docs/dev/evidence/TASK_112/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If determinism regression is already covered by an existing attestation bundle test on origin/main, close out with provenance.
- Stop if pack output currently embeds wall-clock timestamps and removing them would change a documented external contract (escalate via notes).
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
