# TASK_387 — Broader GovMCP maturity restock

SPEC_EXPECTED: DOC

## Objective
Create the bounded broader-GovMCP maturity continuation workfront that advances GovMCP beyond the now-landed minimum required path without widening into broad connector redesign. This restock is spec-and-planning only.

## Scope
- Define the narrow broader-GovMCP maturity task family for `TASK_388` through `TASK_390`.
- Carry forward the current canonical baseline explicitly:
  - GovLayer-core trust-grade closure is landed baseline.
  - GovMCP bounded minimum required-path closure is landed baseline.
- Re-enter GovMCP at the next sharply bounded maturity seam rather than at broad server/connector scope.
- Add queue entries that stage the lane in dependency order.

## Exclusions
- No application/runtime/source changes.
- No tests.
- No broad connector redesign.
- No broad `mcp/server.py` rewrite.
- No reopening of the landed GovLayer-core trust-grade or bounded GovMCP minimum-path claims absent contradictory evidence.
- No edits to `docs/dev/ASSIGNMENTS.md`.

## Allowlist
- `docs/dev/WORK_QUEUE.md`
- `docs/dev/tasks/ready/TASK_387__broader_govmcp_maturity_restock.md`
- `docs/dev/tasks/ready/TASK_388__broader_govmcp_maturity_seam_map.md`
- `docs/dev/tasks/ready/TASK_389__broader_govmcp_maturity_closure_plan.md`
- `docs/dev/tasks/ready/TASK_390__broader_govmcp_maturity_evidence_and_acceptance.md`

## Acceptance criteria
- `TASK_387` exists as a valid restock spec for the broader-GovMCP maturity lane.
- `TASK_388`, `TASK_389`, and `TASK_390` exist as distinct execution-ready tasks.
- `docs/dev/WORK_QUEUE.md` contains queue entries for `TASK_387` through `TASK_390` in repo table format.
- The lane is explicitly focused on broader GovMCP maturity beyond the landed minimum path.
- Each follow-on task contains objective, scope, exclusions, allowlist, acceptance criteria, and stop rules.

## Stop rules
- STOP if task-spec or queue format cannot be determined safely from repo evidence.
- STOP if adding this lane would require editing non-allowlisted files.
- STOP if `TASK_387` through `TASK_390` collide with existing task IDs on current main or remote.
- STOP if the lane cannot remain spec-and-planning only.

## Constraints
- No merge work.
- No implementation work.
- Do not let the lane widen into broad connector or `mcp/server.py` redesign.
- Do not let DevCore workflow/process maturity substitute for GovMCP maturity.
- Preserve current layer boundaries between GovLayer, GovMCP, DevCore, and supporting surfaces.
