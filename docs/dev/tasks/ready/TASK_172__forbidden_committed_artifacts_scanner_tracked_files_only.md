# TASK_172__forbidden_committed_artifacts_scanner_tracked_files_only.md

TASK_ID: TASK_172
Title: [External packaging tranche 2] Forbidden committed artifacts scanner (tracked files only)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_172
Status: Ready
Dependencies: TASK_165
Bucket: External Usability Next

## Goal
Add a deterministic tracked-file scanner test that fails if forbidden local/runtime artifacts are committed to the repository.

## Preconditions
- Git is available and repository can be scanned with `git ls-files`.

## Files allowed to touch
- tests/test_forbidden_repo_artifacts.sh
- docs/dev/evidence/TASK_172/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Tracked-file scanner checks for forbidden artifacts using `git ls-files` only and produces deterministic output.
- Evidence transcript proves two-run stdout digest equality.

## Deterministic test plan
1. Run `tests/test_forbidden_repo_artifacts.sh`.
2. Assert tracked-file list excludes forbidden artifacts (`out/`, `.venv/`, `__pycache__/`, `.DS_Store`, `*.swp`).
3. Run twice and compare stdout digests.

## Evidence required
- docs/dev/evidence/TASK_172/TESTS.txt

## STOP conditions
- Stop if implementation requires scanning untracked files (outside task intent).
- Stop if changes spill outside allowlist.

## Return format
1) Summary
2) Files changed
3) Forbidden artifact classes checked
4) Test command(s) and exit codes
