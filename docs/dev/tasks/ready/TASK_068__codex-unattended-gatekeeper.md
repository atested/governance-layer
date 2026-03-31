# TASK_068__codex-unattended-gatekeeper.md

TASK_ID: TASK_068
Title: Codex unattended gatekeeper runner
Executor: UNASSIGNED
Status: Ready
Dependencies: none

## Goal
Add a fail-closed unattended runner for Codex lane task execution that gates network/repo safety and enforces Allowed Files + evidence + push rules.

## Contract
The runner (`system/scripts/codex-unattended.sh`) must:
- Fail closed on any preflight or verification gate failure.
- Never merge to main.
- Never claim tasks or modify WORK_QUEUE.
- Never modify `docs/dev/ASSIGNMENTS.md`.
- Verify clean tree with local-only exceptions for untracked `.codex/` and optional `ops/CODEX_BATCH.txt` artifact.
- Verify `.git/index.lock` can be created/removed.
- Verify DNS resolution for `github.com`.
- Verify `ssh -T git@github.com` indicates successful authentication.
- For task execution, create/switch `codex/TASK_###` from `origin/main`, parse Allowed Files from task spec, enforce changes are within Allowed Files, require evidence with `TESTS.txt`, commit, and push.

## Required subcommands
1. `preflight`
2. `begin-task TASK_###`
3. `verify-task TASK_###`
4. `finalize-task TASK_### "TASK_###: <title>"`
5. `run-one TASK_### [--no-op] [--verify-only]`
6. `run-list TASK_### TASK_### ...`
7. `run-default-rc` (runs TASK_062..TASK_067)

## Allowed Files parsing rules
Use embedded Python (`fnmatch`) for parsing and matching.
- Parse bullets under either header/label form:
  - `Allowed Files`
  - `Allowed Files:`
- Also tolerate existing task style `Files allowed to touch` blocks.
- Stop parsing at the next markdown header or first blank line after bullet list begins.

## Verification rules
`verify-task` must include changed files from:
- `git diff --name-only` (unstaged tracked)
- `git diff --name-only --cached` (staged tracked)
- untracked entries from `git status --porcelain` (`?? ...`)
- dedupe before matching

Evidence requirements:
- Ensure `docs/dev/evidence/TASK_###/TESTS.txt` exists.
- Fail if evidence directory or `TESTS.txt` is missing.

## Files allowed to touch
- docs/dev/tasks/ready/TASK_068__codex-unattended-gatekeeper.md
- system/scripts/codex-unattended.sh
- docs/dev/OPS_CANONICAL.md
- docs/dev/evidence/TASK_068/**
- docs/dev/inventory/INVENTORY_LATEST.md

## Files forbidden to touch
Everything else, especially:
- docs/dev/ASSIGNMENTS.md
- docs/dev/WORK_QUEUE.md

## Evidence required (TASK_068)
Create `docs/dev/evidence/TASK_068/TESTS.txt` with full output of:
- `bash system/scripts/codex-unattended.sh preflight`
- `bash system/scripts/codex-unattended.sh run-one TASK_062 --no-op`
- `bash system/scripts/codex-unattended.sh run-one TASK_062 --verify-only`

Fallback rule for TASK_062 verify-only testing:
- If `docs/dev/evidence/TASK_062/` does not exist in this working copy, test must demonstrate:
  - Allowed Files parsing works.
  - Branch creation/switch behavior works.
  - Runner fails closed on missing evidence (expected failure) with output captured.

Also include outputs for:
- `bash system/scripts/inventory-snapshot.sh`
- `python3 scripts/verify-ops-canonical.py`

## Acceptance criteria
- Script is executable and `bash -n` clean.
- `preflight` passes on a clean non-main branch and fails on gate violations.
- `begin-task` prints parsed Allowed Files for task spec.
- `verify-task` fails closed when required evidence is missing.
- `verify-ops-canonical.py` returns `OK` with the new script registered.

## Return format
1. Summary
2. Evidence (full command outputs)
3. Notes / deviations
