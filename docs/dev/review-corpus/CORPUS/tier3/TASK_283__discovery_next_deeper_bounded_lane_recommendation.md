# TASK_283 — Discovery next deeper bounded lane recommendation

SPEC_EXPECTED: DOC

## Intent
Perform bounded current-main discovery across recently active live surfaces, evaluate 2 to 4 plausible continuation lanes, and recommend exactly one preferred next deeper lane with explicit rationale. This task is discovery/restock only and must not implement any product/code changes.

## Acceptance criteria
- Current origin-backed live surfaces are inventoried with concrete repo evidence.
- 2 to 4 plausible bounded continuation lanes are identified and compared.
- Comparison explicitly evaluates same-surface continuity, ambiguity, hot-file risk, architecture sensitivity, continuation depth, bounded mergeability, and Codex-to-Cecil conversion likelihood.
- Exactly one preferred lane is recommended and non-chosen candidates are explicitly deferred with rationale.
- No implementation/code surfaces are modified.

## Files allowed to touch
- docs/dev/tasks/ready/TASK_283__discovery_next_deeper_bounded_lane_recommendation.md
- docs/dev/WORK_QUEUE.md
- docs/dev/evidence/TASK_283/**

## Files forbidden to touch
- docs/dev/ASSIGNMENTS.md
- capabilities/capability-registry.json
- mcp/server.py
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/codex-unattended.sh
- Any implementation/code files outside discovery artifacts.
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_283/VALIDATION.txt
- docs/dev/evidence/TASK_283/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_283/DIFF_STAT.txt
- docs/dev/evidence/TASK_283/HOTFILE_SCAN.txt

## Evidence expectations
- Candidate ranking and recommendation are grounded in origin-backed current-main history and current repo shape.
- Evidence includes concrete file/surface references for each candidate lane.

## STOP rules
- STOP if clean-tree or execution-root gates fail.
- STOP if discovery requires touching forbidden files.
- STOP if no defensible recommendation can be made without Cecil-level architecture judgment.

## Constraints
- No implementation.
- No merge work.
- No doctrine rewrite.
- No stale-branch recovery.
- No server integration.
- No cross-surface architecture changes.
