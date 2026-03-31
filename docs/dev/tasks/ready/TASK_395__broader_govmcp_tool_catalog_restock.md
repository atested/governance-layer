# TASK_395 — Broader GovMCP tool-catalog maturity restock

SPEC_EXPECTED: DOC

## Objective
Create the bounded broader-GovMCP tool-catalog maturity continuation workfront that advances GovMCP usefully beyond the landed minimum required-path and inspectability/query seam closures without widening into broad connector redesign.

## Scope
- Define the narrow task family for `TASK_396` through `TASK_398`.
- Carry forward the current baseline explicitly:
  - GovLayer-core trust-grade closure is landed baseline.
  - GovMCP bounded minimum required-path closure is landed baseline.
  - GovMCP bounded inspectability/query seam closure is landed baseline.
  - Broader GovMCP tool-catalog maturity is the refreshed canonical next-workfront recommendation.
- Translate that recommendation into bounded execution-ready analysis/spec tasks.
- Add queue entries in dependency order.

## Exclusions
- No application/runtime/source changes.
- No tests.
- No broad connector redesign.
- No broad `mcp/server.py` rewrite.
- No reopening of the landed GovLayer-core trust-grade, GovMCP minimum-path, or GovMCP inspectability/query claims absent contradictory evidence.
- No edits to `docs/dev/ASSIGNMENTS.md`.

## Allowlist
- `docs/dev/WORK_QUEUE.md`
- `docs/dev/tasks/ready/TASK_395__broader_govmcp_tool_catalog_restock.md`
- `docs/dev/tasks/ready/TASK_396__broader_govmcp_tool_catalog_seam_map.md`
- `docs/dev/tasks/ready/TASK_397__broader_govmcp_tool_catalog_closure_plan.md`
- `docs/dev/tasks/ready/TASK_398__broader_govmcp_tool_catalog_evidence_and_acceptance.md`

## Acceptance criteria
- `TASK_395` exists as a valid restock spec for the broader GovMCP tool-catalog maturity lane.
- `TASK_396`, `TASK_397`, and `TASK_398` exist as distinct execution-ready tasks.
- `docs/dev/WORK_QUEUE.md` contains queue entries for `TASK_395` through `TASK_398` in repo table format.
- The lane is explicitly focused on bounded broader GovMCP tool-catalog maturity.
- Each follow-on task contains objective, scope, exclusions, allowlist, acceptance criteria, and stop rules.

## Stop rules
- STOP if task-spec or queue format cannot be determined safely from repo evidence.
- STOP if adding this lane would require editing non-allowlisted files.
- STOP if `TASK_395` through `TASK_398` collide with existing task IDs on current main or remote.
- STOP if the lane cannot remain spec-and-planning only.

## Constraints
- No merge work.
- No implementation work.
- Do not let the lane widen into broad connector or `mcp/server.py` redesign.
- Do not let proof/export or DevCore workflow substitute for tool-catalog maturity closure.
- Preserve current layer boundaries between GovLayer, GovMCP, DevCore, and supporting surfaces.
