# TASK_123__docs_attestation_bundle_v1_tasking_and_test_catalogue_entry.md

TASK_ID: TASK_123
Title: Docs: attestation bundle v1 tasking and test catalogue entry
Executor: Cecil
Owner/Gate: Greg
Branch: codex/TASK_123
Status: Ready
Dependencies: none
Bucket: Docs / process (optional)

## Goal
Add docs references for planned attestation bundle v1 commands/tests so future implementations have a single documented target.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- docs/TEST-SUITE.md
- docs/dev/ATTESTATION_SPEC.md
- docs/dev/evidence/TASK_123/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_123/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- Docs mention planned bundle pack/verify/determinism/tamper tests with stable IDs/placeholders.
- No implementation code changes are made.
- Evidence captures exact docs diff and grep output.

## Deterministic test plan (commands)
- `rg -n "attestation bundle|bundle verifier|determinism|tamper" docs/dev/ATTESTATION_SPEC.md docs/TEST-SUITE.md`

## Evidence required
- `docs/dev/evidence/TASK_123/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If docs already contain equivalent attestation bundle v1 tasking/test catalogue entries, close out with provenance.
- Stop if referenced doc path(s) do not exist on origin/main.
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
