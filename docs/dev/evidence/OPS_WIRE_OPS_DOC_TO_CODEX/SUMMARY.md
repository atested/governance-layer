# Summary: Wire Ops Process Doc to Codex Auto-Loading

## Goal

Set up Codex to automatically load and prepend `docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md` to every execution run, ensuring all Codex runs receive the canonical ops process guidance without Greg needing to mention it in every tasking.

## Changes Made

### 1. Modified `system/scripts/codex-unattended.sh`

Added ops process doc auto-loading to `cmd_execute_task()` function:
- Loads `docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md` before execution contract construction
- Fail-closed guards: exits with error if ops doc is missing or unreadable
- Prepends ops doc content to execution contract before EXECUTION CONTRACT section
- Every Codex run now automatically receives the full ops process as mandatory preamble

### 2. Created `AGENTS.md`

Added top-level agent reference document at repo root:
- Brief overview of agent roles (ChatGPT, Codex, Cecil, Greg)
- Pointer to canonical ops process doc
- Quick reference for each agent's responsibilities

### 3. Added Verification Test

Created `tests/test_codex_ops_doc_loading.sh`:
- Verifies ops doc exists and is referenced in codex-unattended.sh
- Validates fail-closed guards for missing/unreadable ops doc
- Confirms ops doc prepending logic is present
- Checks ops doc contains expected content snippets
- All 8 test cases pass

## Evidence

See `TESTS.txt` for test execution output with deterministic verification.

## Impact

- **Codex**: Every execution now automatically receives ops process context
- **Greg**: No longer needs to manually include ops doc in dispatches
- **Deterministic**: Ops doc path and loading logic are hardcoded and fail-closed
- **Safe**: No changes to existing task execution logic beyond preamble injection

## Files Changed

- `system/scripts/codex-unattended.sh` (modified: ops doc loading in execute-task)
- `AGENTS.md` (created: top-level agent reference)
- `tests/test_codex_ops_doc_loading.sh` (created: verification test)
