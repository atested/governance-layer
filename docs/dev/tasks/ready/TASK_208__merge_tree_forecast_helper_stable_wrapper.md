# TASK_208 — Merge-tree forecast helper stable wrapper

SPEC_EXPECTED: CODE

## Intent
Create a stable merge forecast wrapper that detects conflict markers from `git merge-tree` output.

## Acceptance criteria
- Wrapper takes exactly 3 args: `<base> <left> <right>`.
- Wrapper uses deterministic output format and exit codes.
- Wrapper script body avoids `$()` command substitution usage.

## Files allowed to touch
- system/tools/merge_tree_forecast.sh
- system/tests/test_merge_tree_forecast.sh
- docs/dev/evidence/TASK_208/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_208/TESTS.txt
- docs/dev/evidence/TASK_208/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_208/DIFF_STAT.txt
- docs/dev/evidence/TASK_208/HOTFILE_SCAN.txt

## Determinism expectations
- run1/run2 stdout SHA256 must match.

## STOP rules
- STOP if deterministic output cannot be produced without hot-file edits.
