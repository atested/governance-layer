# Broader GovMCP Maturity Seam Map v1

## Objective

Identify the next sharply bounded broader GovMCP maturity seam beyond the already-landed minimum required path, using current-main repo evidence rather than generic maturity language.

## Evidence Basis

This map is grounded in current repo surfaces that define or exercise GovMCP runtime, receipt, replay, tool-event, tool-catalog, and exposure behavior:

- `mcp/storage_contract.py`
- `mcp/capability_introspection.py`
- `mcp/tool_event_store.py`
- `mcp/tool_event_link_store.py`
- `mcp/tool_catalog_store.py`
- `mcp/server.py`
- `mcp/README.md`
- `docs/dev/APPLICATIONS_INDEX.md`
- `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`

## Landed Baseline

The already-landed GovMCP minimum required path is treated as baseline input, not as the seam to re-litigate.

Baseline evidence now present on main:

- The mixed-root storage contract is explicit:
  - receipts and receipt-linked indexes under `out/mcp_exec`
  - tool-event indexes and bundles under `$GOV_RUNTIME_DIR/TOOL_EVENTS`
  - tool-catalog state under `out/mcp_tool_catalog`
- Receipt retrieval is materially present through the GovMCP capability/introspection and exposure surfaces.
- Replay linkage from retrieved receipts is materially present.
- Receipt-linked tool-event continuity is materially present through:
  - persisted receipt-to-tool-event link indexes
  - runtime-rooted tool-event indexes
  - bridging lookups in `mcp/tool_event_link_store.py`
- Exposure-layer alignment for the minimum path is materially present without requiring a broad server rewrite.

This means the next seam should extend GovMCP maturity beyond the landed minimum path instead of re-opening storage-contract closure or receipt-to-tool-event continuity as if they were still unresolved blockers.

## Candidate Seams

### Candidate A: Receipt-Linked Inspectability and Query Consistency

#### What is already baseline

- Receipt creation, retrieval, and replay linkage are already landed.
- `mcp/capability_introspection.py` already exposes receipt-oriented load, replay, and event-linkage helpers.
- `mcp/tool_event_link_store.py` already supports receipt-to-tool-event and tool-event-to-receipt lookup.
- `mcp/server.py` already exposes receipt and replay operations for the bounded minimum path.

#### What remains thin, inconsistent, adjacent, or under-proven

- The repo now proves continuity, but not yet a sharply bounded, canonical inspectability/query contract beyond that minimum path.
- Receipt-centered inspectability is spread across multiple helpers and stores rather than being explicitly framed as the next mature GovMCP capability tier.
- Query/report semantics around receipt-linked tool-event state appear functional but still thin in terms of canonical expectations, consistency boundaries, and acceptance proof beyond the minimum path.
- The minimum-path landing proves the path works; it does not yet establish a broader, operator-facing maturity claim for consistent inspection of receipt-linked state.

#### Why it is a strong next seam

- It extends the newly landed minimum path rather than abandoning it.
- It is GovMCP-native rather than cross-cutting.
- It can be bounded around receipt/tool-event introspection and consistency instead of broad connector redesign.
- It improves actual GovMCP usability without defaulting to `mcp/server.py` as the primary target.

#### Why it is not already closed

- Current evidence supports continuity, not a fully articulated broader inspectability maturity tier.
- The repo lacks a canonical statement that defines what broader receipt-linked inspectability consistency should guarantee beyond the minimum path.

### Candidate B: Tool-Event Bundle and Export Maturity

#### What is already baseline

- `mcp/tool_event_store.py` maintains tool-event indexes and bundle locations under the runtime-rooted contract.
- Runtime bundle references and event-bundle storage exist.

#### What remains thin, inconsistent, adjacent, or under-proven

- Bundle/export-oriented maturity is not framed as part of the landed minimum path.
- The repo does not currently show that bundle/export behavior is the highest-leverage next GovMCP seam.
- This area starts to overlap with cross-cutting proof/export concerns rather than staying purely inside broader GovMCP maturity.

#### Why it is not the best next seam

- It is more supportive and evidence-oriented than directly user-facing for GovMCP maturity.
- It risks collapsing the lane into cross-cutting proof/export work rather than a sharply bounded GovMCP continuation.

### Candidate C: Tool-Catalog Inspectability and Maturity

#### What is already baseline

- `mcp/tool_catalog_store.py` already provides persistent catalog storage and listing helpers.
- Tool-catalog state has an explicit location in the mixed-root storage contract.

#### What remains thin, inconsistent, adjacent, or under-proven

- The repo does not currently prove that tool-catalog maturity is required for the next best GovMCP step.
- Tool-catalog functionality remains supporting rather than constitutive to the already-landed minimum path.
- Current README framing keeps tool-catalog explicitly outside the default blocker path.

#### Why it is not the best next seam

- It is a plausible later GovMCP maturity lane, but current evidence makes it look supporting rather than highest-leverage.
- Selecting it now would promote a supporting surface over a more core receipt-linked maturity continuation.

### Candidate D: Broader MCP Exposure-Layer Surface Consistency

#### What is already baseline

- `mcp/server.py` exposes receipt, replay, and related query surfaces.
- The minimum-path exposure alignment has already landed for the bounded path.

#### What remains thin, inconsistent, adjacent, or under-proven

- Broader exposure-surface consistency beyond the minimum path is not yet framed as a bounded maturity seam.
- The server surface is architecture-sensitive and wide enough that a maturity lane can easily sprawl into broad connector redesign.

#### Why it is not the best next seam

- Current evidence does not make `mcp/server.py` the unavoidable center of the next lane.
- Defaulting to server-surface maturity would violate the current constraint to avoid broad connector or server redesign unless the seam map proves it necessary.

## Supporting and Adjacent Surfaces

The following remain important but should not be confused with the recommended next broader GovMCP maturity seam:

- Tool-catalog expansion or richer tool-catalog ergonomics
- Bundle/export or proof-oriented helper surfaces
- DevCore workflow/process maturity
- GovLayer-core trust-grade functionality, which is now baseline input
- Broad MCP surface cleanup or generic API consistency work detached from a sharply bounded maturity seam

## Recommended Next Seam

The recommended next broader GovMCP maturity seam is:

**Receipt-linked inspectability and query consistency beyond the minimum required path.**

## Why This Seam Beats the Alternatives Now

This seam beats the alternatives now because:

- It builds directly on the landed required-path baseline instead of re-opening it.
- It targets the most product-relevant next step in GovMCP usability: not just making the path work, but making the receipt-linked state around that path consistently inspectable and queryable.
- It stays inside GovMCP-native behavior rather than drifting into cross-cutting proof/export concerns.
- It can be closed through bounded introspection/query/contract work without requiring a broad `mcp/server.py` rewrite.
- It leaves tool-catalog and bundle/export surfaces correctly classified as supporting unless later evidence proves otherwise.

## Evidence That Would Change the Seam Choice

The seam choice should change only if repo-grounded evidence shows one of the following:

- Tool-catalog maturity is actually required for normal operator use of the next GovMCP tier, rather than merely supporting it.
- Bundle/export behavior is proven to be the real next bottleneck for GovMCP usefulness rather than a cross-cutting evidence concern.
- The inspectability/query seam cannot be closed without a broader server-surface redesign, making it no longer sharply bounded.
- Current-main evidence reveals a more sharply bounded, higher-leverage GovMCP seam that improves usability more directly than receipt-linked inspectability consistency.

## Constraints for TASK_389

`TASK_389` should be constrained as follows:

- Plan closure around receipt-linked inspectability/query consistency, not around re-opening the already-landed minimum path.
- Keep the closure plan bounded to receipt, replay, and tool-event inspectability/query semantics that extend the landed baseline.
- Do not default to broad `mcp/server.py` work; use server changes only if they are downstream of a narrower introspection/contract need.
- Treat tool-catalog, bundle/export, and DevCore workflow as supporting or adjacent unless repo evidence proves they are necessary to close the selected seam.
- Preserve GovLayer-core trust-grade behavior as baseline input, not as part of the seam.

## Constraints for TASK_390

`TASK_390` should be constrained as follows:

- Define evidence and acceptance for the selected inspectability/query seam, not for generic GovMCP maturity.
- Require proof that the already-landed minimum path remains intact while broader receipt-linked inspectability/query behavior becomes more coherent and demonstrable.
- Include negative cases that distinguish:
  - minimum-path continuity from broader inspectability maturity
  - supporting surfaces from constitutive seam closure
  - narrow inspectability/query closure from broad server/API cleanup
- Avoid acceptance criteria that can be satisfied merely by tool-catalog presence, bundle/export helpers, or DevCore process maturity.

## Decision Summary

- Recommended next seam: `receipt-linked inspectability and query consistency beyond the minimum required path`
- Strongest alternatives considered: tool-event bundle/export maturity, tool-catalog maturity, broader exposure-layer consistency
- Why selected: best leverage, clearest boundedness, strongest extension of the landed baseline, lowest risk of connector redesign sprawl
