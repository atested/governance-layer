# TASK_375 — GovMCP required-path closure restock

SPEC_EXPECTED: DOC

## Objective
Create the bounded GovMCP required-path closure implementation lane that translates the three minimum implied implementation fronts into execution-ready tasks for storage-contract closure, receipt-to-tool-event continuity closure, and bounded exposure-layer alignment. This restock is spec-and-planning only.

## Scope
- Define the narrow GovMCP blocker-closure task family for `TASK_376` through `TASK_378`.
- Carry forward the established blocker shape explicitly: split-root required-path continuity across `GOV_RUNTIME_DIR` and `out/`, not missing GovLayer-core trust-grade behavior.
- Add queue entries that stage the lane in dependency order.
- Preserve the distinction between GovMCP blocker fixes, GovLayer-core baseline dependencies, DevCore-adjacent dependencies, and supporting but non-blocking inspectability surfaces.

## Exclusions
- No GovMCP implementation changes.
- No broad connector rewrite.
- No GovLayer-core re-hardening.
- No DevCore workflow/process redesign.
- No tests or application/runtime/source changes.
- No edits to `docs/dev/ASSIGNMENTS.md`.

## Allowlist
- `docs/dev/WORK_QUEUE.md`
- `docs/dev/tasks/ready/TASK_375__govmcp_required_path_closure_restock.md`
- `docs/dev/tasks/ready/TASK_376__govmcp_storage_contract_closure.md`
- `docs/dev/tasks/ready/TASK_377__govmcp_receipt_to_tool_event_continuity.md`
- `docs/dev/tasks/ready/TASK_378__govmcp_exposure_layer_alignment.md`

## Acceptance criteria
- `TASK_375` exists as a valid restock spec for the GovMCP required-path closure lane.
- `TASK_376`, `TASK_377`, and `TASK_378` exist as distinct execution-ready tasks.
- `docs/dev/WORK_QUEUE.md` contains queue entries for `TASK_375` through `TASK_378` in repo table format.
- The lane is explicitly centered on GovMCP required-path closure, not broad MCP rewrite work.
- Each follow-on task contains objective, scope, exclusions, allowlist, acceptance criteria, and stop rules.

## Stop rules
- STOP if task-spec or queue format cannot be determined safely from repo evidence.
- STOP if adding this lane would require editing non-allowlisted files.
- STOP if `TASK_375` through `TASK_378` collide with existing task IDs on the authoritative baseline or remote.
- STOP if the lane cannot remain spec-and-planning only.

## Constraints
- No merge work.
- No reorg/blocker-loop reopening.
- Do not count GovLayer-core trust-grade completion as GovMCP closure.
- Do not let DevCore workflow maturity substitute for required-path closure.
- Do not silently promote tool-catalog or bundle/export surfaces into the minimum blocker path unless later repo evidence requires it.

