# TASK_110__attestation_bundle_v1_deterministic_pack_command.md

TASK_ID: TASK_110
Title: Attestation bundle v1: deterministic pack command
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_110
Status: Ready
Dependencies: none
Bucket: Attestation bundle v1

## Goal
Add a deterministic attestation bundle pack command that emits a manifest and artifact set with stable ordering and hashes.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- scripts/attest/bundle.py
- tests/test_attestation_bundle_pack.sh
- tests/fixtures/attestation_bundle/**
- docs/dev/evidence/TASK_110/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_110/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- `scripts/attest/bundle.py` can build a bundle from fixed fixtures into a temp output directory.
- Manifest ordering and bundle hash are stable across two runs with identical inputs.
- `tests/test_attestation_bundle_pack.sh` exits 0 and prints the deterministic hash comparison.

## Deterministic test plan (commands)
- `bash tests/test_attestation_bundle_pack.sh`

## Evidence required
- `docs/dev/evidence/TASK_110/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If an equivalent attestation bundle pack command and deterministic test already exist on origin/main, do not re-implement; convert to evidence-closeout with provenance.
- Stop if the implementation would require adding external dependencies not already used by the repo.
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
