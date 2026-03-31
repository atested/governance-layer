# Wrong Execution Root Operator Note

## Purpose
Use this note when a dispatch requires a specific execution root and a command is about to run outside it.

## WRONG_EXECUTION_ROOT handling
- Detect current working directory before git operations.
- If the directory is outside the required execution root, stop immediately.
- Emit a canonical STOP PACKET and do not continue with task execution.

## Canonical STOP PACKET shape
STOP PACKET
- Timestamp: <ISO-8601 UTC>
- Repo: <absolute path>
- Step failed: WRONG_EXECUTION_ROOT
- Command: <command that would have run>
- Output: <deterministic reason string>
- git status --porcelain: <verbatim snapshot>

## Deterministic example
STOP PACKET
- Timestamp: 2026-02-28T00:00:00Z
- Repo: /Users/gregkeeter/codex-workspaces/governance-layer
- Step failed: WRONG_EXECUTION_ROOT
- Command: git fetch origin --prune
- Output: current directory is outside required execution root
- git status --porcelain: ?? out/
