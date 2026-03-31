# TASK_165__repo_packaging_check_tree_completeness_and_forbidden_local_artifacts.md

TASK_ID: TASK_165
Title: [External packaging] Repo packaging check (tree completeness + forbidden local artifacts)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_165
Status: Ready
Dependencies: none
Bucket: External Usability Next

## Goal
Add a deterministic repo packaging check that validates required externally-facing files are present and obvious local-only artifacts are absent from the repository tree.

## Preconditions
- `README.md`, `docs/EXTERNAL_CONTRACTS.md`, and `docs/TEST-SUITE.md` exist on origin/main.
- Repository can be scanned without network access.

## Files allowed to touch
- tests/test_repo_packaging_check.sh
- docs/dev/evidence/TASK_165/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/bootstrap-run.sh
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Deterministic test validates required top-level docs/scripts are present.
- Deterministic test validates absence of obvious local-only artifacts (`.DS_Store`, `*.swp`, `__pycache__/`, `.venv/`, `out/`).
- Transcript includes two-run digest equality of normalized stdout.

## Deterministic test plan
1. Run `tests/test_repo_packaging_check.sh`.
2. Assert required file presence and forbidden-artifact absence with stable PASS/FAIL markers.
3. Compare stdout digest across two runs.

## Evidence required
- docs/dev/evidence/TASK_165/TESTS.txt

## STOP conditions
- Stop if required checks need to modify repo files (this task is tests/evidence only).
- Stop if changes spill outside the allowlist.

## Return format
1) Summary
2) Files changed
3) Packaging checks enforced
4) Test command(s) and exit codes

