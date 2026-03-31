# TASK_189__bash_portability_regression_scan_for_external_scripts_and_tests.md

TASK_ID: TASK_189
Title: [External readiness regressions] Bash portability regression scan for external scripts/tests
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_189
Status: Ready
Dependencies: none
Bucket: External Usability Next
SPEC_EXPECTED: CODE

## Goal
Add a deterministic scan that guards external scripts/tests against common Bash 4+ features not available on macOS Bash 3.2.

## Preconditions
- Git is available to enumerate tracked shell scripts deterministically.

## Files allowed to touch
- tests/test_external_bash_portability_scan.sh
- docs/dev/evidence/TASK_189/**

## Files forbidden to touch
- Everything else

## Output expectations (Done)
- Test scans tracked `tests/*.sh` and `system/scripts/*.sh`.
- Forbidden feature patterns are reported in sorted order with stable output.
- If no offenders are found, test passes with deterministic output and digest proof.

## Deterministic test plan
1. Enumerate tracked shell scripts via `git ls-files` with sorted ordering.
2. Scan for forbidden Bash 4+ patterns (`mapfile`, `readarray`, `declare -A`).
3. Run the scan twice and compare normalized stdout digests.

## Evidence required
- docs/dev/evidence/TASK_189/TESTS.txt

## STOP conditions
- Stop if task requires edits outside allowlist.

## Return format
1) Summary
2) Files changed
3) Scan result (offenders or PASS)
4) Determinism digest proof
