# TASK_119__ops_canonical_verifier_regression_tests_for_forbidden_command_block_exceptions.md

TASK_ID: TASK_119
Title: OPS_CANONICAL verifier: regression tests for forbidden-command block exceptions
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_119
Status: Ready
Dependencies: none
Bucket: Governance tooling / gates

## Goal
Add regression tests for verify-ops-canonical scoped forbidden-keyword ignore blocks plus negative controls.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- scripts/verify-ops-canonical.py
- tests/test_verify_ops_canonical.sh
- docs/dev/evidence/TASK_119/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_119/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- `tests/test_verify_ops_canonical.sh` proves documented forbidden-command list blocks are ignored and real violations still fail.
- Tests run deterministically without touching production scripts beyond temp fixtures.
- Verifier behavior remains fail-closed outside delimited blocks.

## Deterministic test plan (commands)
- `bash tests/test_verify_ops_canonical.sh`

## Evidence required
- `docs/dev/evidence/TASK_119/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If equivalent verifier regression tests already exist, close out with provenance.
- Stop if implementation would weaken verifier enforcement beyond documented block exceptions.
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
