# TASK_120__mcp_smoke_deterministic_failure_mode_expansion_for_unsupported_invalid_tool_paths.md

TASK_ID: TASK_120
Title: MCP smoke: deterministic failure-mode expansion for unsupported/invalid tool paths
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_120
Status: Ready
Dependencies: none
Bucket: MCP smoke + policy completeness

## Goal
Expand MCP smoke coverage with deterministic failure-mode checks for unsupported tool names or invalid request shapes.

## Non-goals
- No changes outside the allowed files list.
- No force-push or branch management workflow changes.
- No unrelated refactors.

## Files allowed to touch
- tests/run-mcp-smoke.py
- tests/run-mcp-smoke.sh
- mcp/server.py
- docs/dev/evidence/TASK_120/**

## Files forbidden to touch
- Everything else

## Procedure
1) Confirm the target behavior is not already implemented on origin/main using the deterministic test or file precheck commands below.
2) Implement the smallest change that satisfies the goal and keeps outputs deterministic.
3) Add/extend tests in the allowed paths and run the deterministic test plan.
4) Record evidence in `docs/dev/evidence/TASK_120/TESTS.txt` with `$` command lines and `[exit=...]` markers.

## Success criteria
- Smoke tests cover at least one new deterministic failure mode and assert stable output/exit behavior.
- Changes do not introduce timing-dependent assertions.
- Evidence captures the new smoke pass output.

## Deterministic test plan (commands)
- `bash tests/run-mcp-smoke.sh`

## Evidence required
- `docs/dev/evidence/TASK_120/TESTS.txt`
- `git diff --name-only origin/main...HEAD`
- `git diff --stat origin/main...HEAD`
- Full command transcripts for the deterministic test plan above

## STOP conditions
- If the targeted failure modes are already covered in smoke, close out with provenance.
- Stop if testing requires live network or non-deterministic external services.
- If work is already implemented on origin/main, do not duplicate it; report provenance and request reconciliation/evidence-closeout instead.

## Return format
1) Summary
2) Files changed
3) Test command(s) + result summary
4) Evidence paths
