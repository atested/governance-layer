# TASK_391 — Broader GovMCP inspectability/query consistency restock

SPEC_EXPECTED: DOC

## Objective
Create the bounded broader-GovMCP inspectability/query consistency implementation workfront that advances the selected receipt-linked maturity seam beyond the landed minimum required path without widening into broad connector redesign.

## Scope
- Define the narrow implementation task family for `TASK_392` through `TASK_394`.
- Carry forward the current baseline explicitly:
  - GovLayer-core trust-grade closure is landed baseline.
  - GovMCP bounded minimum required-path closure is landed baseline.
  - The selected broader seam is receipt-linked inspectability/query consistency beyond that minimum path.
- Translate the minimum implied implementation fronts from `TASK_389` and `TASK_390` into bounded execution-ready tasks.
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
- `docs/dev/tasks/ready/TASK_391__broader_govmcp_inspectability_restock.md`
- `docs/dev/tasks/ready/TASK_392__govmcp_canonical_inspectability_query_contract.md`
- `docs/dev/tasks/ready/TASK_393__govmcp_receipt_replay_tool_event_consistency_alignment.md`
- `docs/dev/tasks/ready/TASK_394__govmcp_narrow_exposure_alignment_for_inspectability.md`

## Acceptance criteria
- `TASK_391` exists as a valid restock spec for the broader GovMCP inspectability/query consistency lane.
- `TASK_392`, `TASK_393`, and `TASK_394` exist as distinct execution-ready tasks.
- `docs/dev/WORK_QUEUE.md` contains queue entries for `TASK_391` through `TASK_394` in repo table format.
- The lane is explicitly focused on the selected broader GovMCP inspectability/query seam.
- Each follow-on task contains objective, scope, exclusions, allowlist, acceptance criteria, and stop rules.

## Stop rules
- STOP if task-spec or queue format cannot be determined safely from repo evidence.
- STOP if adding this lane would require editing non-allowlisted files.
- STOP if `TASK_391` through `TASK_394` collide with existing task IDs on current main or remote.
- STOP if the lane cannot remain spec-and-planning only.

## Constraints
- No merge work.
- No implementation work.
- Do not let the lane widen into broad connector or `mcp/server.py` redesign.
- Do not let tool-catalog, proof/export, or DevCore workflow substitute for closure of the selected seam.
- Preserve current layer boundaries between GovLayer, GovMCP, DevCore, and supporting surfaces.
