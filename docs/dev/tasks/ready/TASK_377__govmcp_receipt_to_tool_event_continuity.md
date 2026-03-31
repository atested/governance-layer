# TASK_377 — GovMCP receipt-to-tool-event continuity

SPEC_EXPECTED: DOC

## Objective
Produce the bounded implementation-ready task that closes receipt-linked continuity across the minimum GovMCP required path, including receipt emission and retrieval linkage, replay linkage, and receipt-linked tool-event continuity under the canonical storage contract.

## Scope
- Use the storage contract closed by `TASK_376` as the authority for required-path continuity.
- Close the path from emitted receipt to retrievable receipt to replay check to linked tool-event inspectability.
- Make receipt-linked continuity explicit and testable rather than stitched together through implicit root assumptions.
- Preserve the rule that tool-catalog surfaces stay excluded unless later evidence proves they are required to keep the minimum path intelligible.

## Exclusions
- No broad MCP feature expansion.
- No tool-catalog expansion unless proven required for the minimum path.
- No GovLayer-core trust-grade rework.
- No DevCore process redesign.
- No broad server rewrite.

## Allowlist
- `mcp/capability_introspection.py`
- `mcp/tool_event_store.py`
- `mcp/tool_event_link_store.py`
- `mcp/server.py` only if minimal continuity alignment requires it
- bounded supporting docs/tests directly required to validate required-path continuity

## Acceptance criteria
- The path from receipt emission to retrieval to replay linkage to receipt-linked tool-event continuity is explicit and coherent.
- Continuity no longer depends on undocumented cross-root assumptions.
- The task preserves explicit exclusion of tool-catalog expansion unless current execution evidence proves it is required.
- GovLayer-core trust-grade behavior remains a baseline dependency, not closure proof.
- The result gives `TASK_378` a stable continuity contract for exposure-layer alignment.

## Stop rules
- STOP if continuity closure would require broad MCP rewrite rather than bounded required-path work.
- STOP if the task would rely on DevCore process maturity instead of end-to-end continuity.
- STOP if the path cannot be closed honestly without silently promoting supporting surfaces into the minimum blocker path.

## Constraints
- Keep the task centered on the minimum required path only.
- Treat replay linkage as constitutive continuity, not optional evidence garnish.
- Do not treat isolated component health as continuity closure.

