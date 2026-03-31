# TASK_192 — Bash portability remediation for external surface

SPEC_EXPECTED: CODE

## Goal
Restore PASS for `tests/test_external_bash_portability_scan.sh` by eliminating false positives and/or bash4-only usage within the scanned external surface, while keeping output deterministic.

## Preconditions
- `tests/test_external_bash_portability_scan.sh` exists on the task branch tip (e.g., via cherry-pick from TASK_189 before implementation).
- Run from repo root.

## Files allowed to touch
- tests/test_external_bash_portability_scan.sh
- docs/dev/evidence/TASK_192/**

## Files forbidden to touch
- Everything else

## Required evidence
- `docs/dev/evidence/TASK_192/TESTS.txt`
- Must include:
  - initial offender list (before remediation)
  - commands executed
  - run1/run2 exit codes after remediation
  - SHA256 digests identical across two runs

## Procedure
1. Run `bash tests/test_external_bash_portability_scan.sh` and capture offenders.
2. Apply the smallest deterministic fix that restores PASS for the intended scan scope.
3. Re-run twice and confirm `RC_RUN1=0`, `RC_RUN2=0` and identical SHA256 digests.
4. Record evidence transcript.

## STOP conditions
- STOP if remediation requires editing any file outside the allowlist.
- If offenders are outside the allowlist, publish a spec-adjustment branch listing the exact files instead of widening to globs.

## Done when
- `tests/test_external_bash_portability_scan.sh` passes twice deterministically.
- Evidence transcript is recorded under the required path.
