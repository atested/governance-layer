# Broader GovMCP Maturity Closure Plan v1

## Objective

Define the minimum changes required to close the selected broader GovMCP maturity seam:

**receipt-linked inspectability and query consistency beyond the landed minimum required path**

This plan extends the landed minimum path. It does not reopen storage-contract closure, receipt retrieval, replay linkage, or receipt-to-tool-event continuity as if those were still unresolved blockers.

## Governing Seam

This plan is derived directly from [BROADER_GOVMCP_MATURITY_SEAM_MAP__v1.md](/Volumes/SSD/ai-systems/codex-workspaces/governance-layer/docs/dev/BROADER_GOVMCP_MATURITY_SEAM_MAP__v1.md).

Selected seam:

- make receipt-linked state more coherently inspectable and queryable
- keep that seam narrower than broad connector redesign
- preserve the already-landed minimum path as baseline input

## Current Baseline

Current repo evidence already provides:

- explicit mixed-root storage contract through `mcp/storage_contract.py`
- deterministic receipt load/list behavior through `mcp/capability_introspection.py`
- replay linkage from stored receipts through `replay_check(...)`
- persisted and bridged receipt-to-tool-event / tool-event-to-receipt continuity through `mcp/tool_event_link_store.py`
- bounded exposure support for receipt, replay, tool-event, and receipt-linked queries through `mcp/server.py`

What current evidence does not yet establish as a distinct mature tier:

- a canonical inspectability/query contract above bare minimum continuity
- a clearly bounded expectation for how receipt, replay, and linked tool-event queries should agree with each other
- explicit proof that broader receipt-linked inspection is coherent rather than merely available through separate helpers

## Closure Goal

The seam is closed when GovMCP provides a coherent, bounded receipt-linked inspectability layer in which:

- receipt retrieval
- replay inspection
- direct receipt-to-tool-event lookup
- reverse tool-event-to-receipt lookup
- bounded recent/list query surfaces

all agree on the same underlying receipt-linked state contract strongly enough to support a broader GovMCP maturity claim beyond the minimum path.

This is a maturity closure target, not broad GovMCP completion.

## Minimum Closure Strategy

The shortest credible path is:

1. define a canonical inspectability/query contract around receipt-linked state
2. align the narrow set of introspection/query producers to that contract
3. align only the necessary exposure surfaces downstream of that contract
4. prove the minimum path still holds while inspectability coherence improves

This keeps `mcp/server.py` downstream of narrower introspection/contract work rather than making the server the default first target.

## Minimum Implementation Fronts

### Front A: Canonical Receipt-Linked Inspectability Contract

Purpose:

- define the authoritative set of inspectability/query fields and relationships that must agree across receipt-linked surfaces

Minimum expected closure:

- canonical expectations for receipt identity, digest, replay state, signature state, and `tool_event_digests`
- explicit relationship between:
  - `load_receipt(...)`
  - `replay_check(...)`
  - `get_tool_events_for_receipt(...)`
  - `get_receipts_for_tool_event(...)`
  - bounded recent/list helpers
- explicit statement of what constitutes coherent query behavior beyond mere path continuity

Likely implementation center:

- `mcp/capability_introspection.py`
- `mcp/tool_event_link_store.py`
- possibly narrow helper additions around shared receipt-linked payload shaping

Why this front is first:

- without a narrow contract, later exposure alignment would become generic API cleanup rather than seam closure

### Front B: Query Consistency Alignment Across Receipt, Replay, and Linked Tool-Event Surfaces

Purpose:

- make the narrow set of receipt-linked query paths agree on the same state and semantics

Minimum expected closure:

- receipt-facing and tool-event-facing queries return mutually compatible linkage information
- replay-oriented inspection preserves and exposes the same canonical linkage expectations
- recent/list surfaces do not silently diverge from direct lookup surfaces on the core receipt-linked relationship

Likely implementation center:

- `mcp/capability_introspection.py`
- `mcp/tool_event_link_store.py`
- `mcp/tool_event_store.py`

Boundary:

- do not widen into bundle/export or tool-catalog maturity unless execution evidence later proves they are required

### Front C: Narrow Exposure-Layer Alignment to the Canonical Inspectability Contract

Purpose:

- align only the subset of MCP exposure methods that present the selected seam

Minimum expected closure:

- receipt, replay, receipt-tool-event, tool-event-receipts, and closely related list/query methods expose the same canonical inspectability contract
- no broad `mcp/server.py` rewrite
- no generic endpoint normalization unrelated to the seam

Likely implementation center:

- bounded edits in `mcp/server.py`
- only where needed to reflect the already-closed contract and consistency work underneath

Why this front is downstream:

- exposure alignment should reflect the closed seam, not substitute for it

## True Seam-Closure Changes

The following count as constitutive seam-closure work:

- defining the authoritative inspectability/query contract for receipt-linked state
- aligning receipt, replay, and tool-event linkage semantics to that contract
- making the narrow downstream exposure methods faithfully present the same contract
- proving the minimum path remains intact while the broader inspectability/query contract becomes coherent

## Supporting but Non-Blocking Improvements

The following may be useful but should not be treated as required seam closure by default:

- richer tool-catalog ergonomics
- broader tool-event export polish
- bundle/export verifier ergonomics
- broader server response cleanup outside the selected seam
- generic documentation cleanup outside the seam and its acceptance proof

## Adjacent Surfaces That Must Remain Non-Constitutive

These areas should remain adjacent unless later repo evidence proves otherwise:

- `mcp/tool_catalog_store.py` and tool-catalog-oriented UX
- bundle/export and proof-oriented helper surfaces
- DevCore workflow/process maturity
- GovLayer-core trust-grade capabilities
- broader connector or server redesign

## What This Plan Explicitly Excludes

- reopening the landed minimum-path closure claim
- broad `mcp/server.py` rewrite
- broad GovMCP roadmap redesign
- turning tool-catalog maturity into the selected seam by assumption
- turning proof/export surfaces into seam closure evidence by assumption

## Recommended Execution Order

1. close the canonical inspectability/query contract
2. close consistency across receipt, replay, and tool-event linkage surfaces
3. align the narrow exposure methods to the now-canonical contract
4. verify that minimum-path continuity still holds

## Remaining Ambiguities

The following should stay explicit going into implementation:

- whether recent/list query surfaces need full alignment or only bounded alignment around receipt-linked state
- whether one small shared payload-shaping helper is enough, or whether a more explicit internal inspectability contract module is warranted
- whether any narrow `mcp/server.py` changes are needed beyond response-shape alignment

These are implementation-shape ambiguities, not reasons to widen the lane.

## Planning Decision

The shortest credible closure path is:

**canonical inspectability/query contract -> consistency alignment in receipt/replay/tool-event linkage surfaces -> narrow exposure alignment**

That path keeps the lane sharply bounded, extends the landed minimum path, and avoids broad connector redesign by default.
