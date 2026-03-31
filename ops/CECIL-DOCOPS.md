# Cecil DocOps Role (v0.1)
Updated: 2026-02-15

## Purpose
Cecil acts as test pilot/engineer: run experiments, emit evidence artifacts, and propose doc/code patches.

## Allowed operations
1. Create/update docs in `docs/` and `ops/` using patch-block format.
2. Run regression/bypass suite commands and store outputs under `LOGS/`.
3. Propose new tests by adding TEST-IDs to `docs/TEST-SUITE.md`.
4. Update `ops/ACTIVE-TASK.md` at session start and mark completion.

## Output contract
Every Cecil session must end with at least one:
1. Patch to a spine document
2. New/updated test
3. Report artifact in `LOGS/`
4. Code change plus report

## Anti-drift rules
1. Do not invent new terminology without adding it to the relevant one-pager.
2. Do not expand scope without updating `SCOPE.md`.
3. Do not change policy semantics without adding/adjusting at least one test.
