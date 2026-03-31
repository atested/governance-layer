# TASK_178__external_packaging_meta_runner_determinism_and_ordering.md

TASK_ID: TASK_178
Title: [External validator hardening] Cold-surface meta-runner determinism and ordering
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_178
Status: Ready
Dependencies: TASK_170, TASK_171, TASK_172, TASK_173
Bucket: External Validator Hardening
SPEC_EXPECTED: CODE

## Goal
Add a deterministic regression test for `tests/run_external_packaging_checks.sh` proving stable BEGIN/END ordering, stable rc values, and stable output digest across two runs (with `PROOF_BUNDLE_DIR` unset).

## Preconditions
- `tests/run_external_packaging_checks.sh` exists on the branch tip.

## Files allowed to touch
- tests/test_external_packaging_meta_runner_determinism.sh
- tests/run_external_packaging_checks.sh
- docs/dev/evidence/TASK_178/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- system/scripts/release-gate.sh
- system/scripts/codex-unattended.sh
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Deterministic meta-runner test exists and verifies stable ordering/rcs for the bounded cold-surface suite.
- `tests/run_external_packaging_checks.sh` is edited only if needed to stabilize ordering/messages.
- Evidence transcript records two-run digest equality and PASS markers.

## Deterministic test plan
1. Run `tests/run_external_packaging_checks.sh` twice with `PROOF_BUNDLE_DIR` unset.
2. Normalize output only for allowed nondeterministic fields (if any), then hash.
3. Assert stable BEGIN/END block ordering and stable rc values across runs.

## Evidence required
- docs/dev/evidence/TASK_178/TESTS.txt

## STOP conditions
- Stop if `tests/run_external_packaging_checks.sh` is missing on the branch tip (dependency TASK_173 not merged).
- Stop if stable ordering requires edits outside allowlist.
- Stop if nondeterministic output source cannot be normalized without broad behavior changes.

## Return format
1) Summary
2) Files changed
3) Ordering/rc checks
4) Determinism digest proof
