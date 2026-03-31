# TASK_190__cold_surface_meta_runner_ordering_hardening_regression.md

TASK_ID: TASK_190
Title: [External readiness regressions] Cold-surface meta runner ordering hardening regression
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_190
Status: Ready
Dependencies: TASK_173
Bucket: External Usability Next
SPEC_EXPECTED: CODE

## Goal
Add a deterministic regression test that locks stable ordering and rc-map behavior of `tests/run_external_packaging_checks.sh`.

## Preconditions
- `tests/run_external_packaging_checks.sh` exists on the branch tip.

## Files allowed to touch
- tests/test_external_packaging_meta_runner_ordering_regression.sh
- docs/dev/evidence/TASK_190/**

## Files forbidden to touch
- Everything else

## Output expectations (Done)
- Test runs the meta-runner twice with `PROOF_BUNDLE_DIR` unset.
- Verifies BEGIN/END block ordering stability and rc-map stability.
- Emits deterministic normalized-output digest equality across runs.

## Deterministic test plan
1. Run `bash tests/run_external_packaging_checks.sh` twice with identical env (`PROOF_BUNDLE_DIR` unset).
2. Normalize output (strip absolute temp paths if present).
3. Compare ordered `BEGIN:`/`END:` markers and rc map across runs.
4. Compare normalized stdout digests across runs.

## Evidence required
- docs/dev/evidence/TASK_190/TESTS.txt

## STOP conditions
- Stop if task requires edits outside allowlist.

## Return format
1) Summary
2) Files changed
3) Ordering/rc-map check results
4) Determinism digest proof
