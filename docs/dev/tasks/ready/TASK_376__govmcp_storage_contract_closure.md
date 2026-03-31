# TASK_376 — GovMCP storage-contract closure

SPEC_EXPECTED: DOC

## Objective
Produce the bounded implementation-ready task that makes the authoritative GovMCP storage contract explicit across `GOV_RUNTIME_DIR` and `out/`, including where each required-path artifact lives, what the canonical fallback behavior is, and what narrow bridging logic is needed to make the contract coherent.

## Scope
- Define the authoritative storage contract for the minimum required GovMCP path.
- Close the current ambiguity around what `GOV_RUNTIME_DIR` governs and what remains intentionally rooted under `out/`.
- Identify and implement only the narrow storage/bridging changes needed to support required-path continuity.
- Preserve the distinction between core required-path artifacts, supporting inspectability artifacts, and adjacent non-counting surfaces.

## Exclusions
- No broad storage migration or full root unification unless required by direct repo evidence during execution.
- No broad `mcp/server.py` rewrite.
- No tool-catalog expansion unless needed to preserve the minimum required path.
- No GovLayer-core re-hardening.
- No DevCore process redesign.

## Allowlist
- `mcp/server.py`
- `mcp/capability_introspection.py`
- `mcp/tool_event_store.py`
- `mcp/tool_event_link_store.py`
- `mcp/tool_catalog_store.py`
- `mcp/README.md`
- bounded supporting docs/tests directly required to validate the storage contract

## Acceptance criteria
- The authoritative GovMCP storage contract is explicit across `GOV_RUNTIME_DIR` and `out/`.
- The task defines where each required-path artifact lives and what the canonical fallback behavior is.
- Any bridging logic is narrow and justified by required-path continuity rather than broad cleanup.
- The task preserves explicit exclusions against broad connector/storage rewrite.
- The result gives `TASK_377` a stable storage contract to build continuity on.

## Stop rules
- STOP if closure requires a broad storage migration or connector rewrite rather than a bounded contract fix.
- STOP if the task would count GovLayer-core trust-grade behavior as constitutive GovMCP closure.
- STOP if the task cannot make the contract explicit without widening into non-allowlisted surfaces.

## Constraints
- Keep the task centered on minimum required-path storage closure.
- Treat tool-catalog and bundle/export surfaces as supporting unless execution evidence proves one is mandatory.
- Keep DevCore workflow/process surfaces adjacent and non-counting.

