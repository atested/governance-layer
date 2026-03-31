# Broader GovMCP Maturity Evidence And Acceptance v1

## Objective

Define exact evidence, demonstrations, negative cases, and acceptance criteria for claiming closure of the selected broader GovMCP maturity seam:

**receipt-linked inspectability and query consistency beyond the landed minimum required path**

This acceptance standard is derived from:

- [BROADER_GOVMCP_MATURITY_SEAM_MAP__v1.md](/Volumes/SSD/ai-systems/codex-workspaces/governance-layer/docs/dev/BROADER_GOVMCP_MATURITY_SEAM_MAP__v1.md)
- [BROADER_GOVMCP_MATURITY_CLOSURE_PLAN__v1.md](/Volumes/SSD/ai-systems/codex-workspaces/governance-layer/docs/dev/BROADER_GOVMCP_MATURITY_CLOSURE_PLAN__v1.md)

It does not define generic GovMCP maturity acceptance.

## Acceptance Boundary

The seam is closed only if both of the following are true:

- the already-landed minimum path still works:
  - receipt retrieval
  - replay linkage
  - receipt-to-tool-event continuity
- broader receipt-linked inspectability/query behavior becomes coherently aligned across the selected narrow set of receipt, replay, and tool-event query surfaces

If either side fails, the seam is not closed.

## What Counts As Closure Evidence

Closure evidence must show all of the following:

### 1. Canonical Inspectability Contract Evidence

There is explicit evidence that the selected receipt-linked query surfaces now follow one coherent inspectability contract covering at least:

- receipt identity
- receipt digest state
- replay state
- signature-related state where applicable
- `tool_event_digests`
- receipt-to-tool-event linkage
- tool-event-to-receipt linkage

This evidence can be code-level, doc-level, or test-level, but it must be explicit enough to show that the seam is more mature than isolated helper availability.

### 2. Cross-Surface Query Consistency Evidence

There is evidence that the key selected surfaces agree with each other rather than merely succeeding independently.

Minimum required relationships:

- receipt load agrees with replay inspection on the core receipt identity and digest basis
- receipt-linked tool-event lookup agrees with reverse tool-event-to-receipt lookup
- direct lookup and bounded list/recent views do not contradict the canonical linkage state for the same receipt/tool-event pair

### 3. Minimum-Path Preservation Evidence

There is explicit evidence that the already-landed minimum path still holds after seam-closing changes.

Minimum preserved path:

- receipt exists and loads deterministically
- replay check still runs from the stored receipt
- receipt-to-tool-event continuity still resolves correctly

### 4. Narrow Exposure Alignment Evidence

If exposure-surface changes are part of closure, there must be evidence that they:

- reflect the same canonical inspectability contract
- stay narrow and seam-specific
- do not depend on broad server cleanup

### 5. Anti-Inflation Evidence

There must be at least one explicit negative proof showing the lane did not claim closure from the wrong evidence category.

At least one of these must be demonstrated:

- a minimum-path-only success case does not automatically pass broader seam acceptance
- a broad response cleanup with no coherent inspectability contract does not pass acceptance
- supporting surfaces such as tool-catalog or bundle/export cannot satisfy seam closure by themselves

## Mandatory Demonstrations / Tests

The later execution lane must provide demonstrations or tests that cover all of the following:

### A. Receipt-Linked Inspectability Coherence

Demonstrate that a receipt can be inspected through the selected narrow set of surfaces and yields a coherent view of:

- run/receipt identity
- digest state
- replay-related state
- linked tool-event digests

### B. Query Consistency Across the Selected Seam

Demonstrate consistency across at least:

- receipt load
- replay check
- receipt-to-tool-event lookup
- tool-event-to-receipt lookup

Where bounded list or recent surfaces are included in the implementation, demonstrate they agree with the same canonical linkage state.

### C. Preservation of Minimum-Path Continuity

Demonstrate that seam-closing changes do not regress:

- deterministic receipt retrieval
- replay linkage from stored receipt
- receipt-linked tool-event continuity

### D. Narrow Exposure-Layer Conformance

If exposure methods are updated, demonstrate that only the seam-relevant methods changed and that they present the same canonical inspectability/query semantics defined by the closure plan.

### E. At Least One Negative / Anti-Inflation Case

Demonstrate that the acceptance harness rejects at least one false-closure pattern from the list below.

## False-Closure Cases

The following do **not** count as seam closure:

### False Closure 1: Minimum-Path Success Only

- receipt retrieval works
- replay linkage works
- receipt-to-tool-event continuity works
- but broader inspectability/query semantics remain fragmented or unproven

This proves baseline continuity, not broader maturity seam closure.

### False Closure 2: Isolated Inspectability Improvement

- one receipt or tool-event query becomes richer
- but related receipt/replay/linkage queries do not agree on the same canonical state

This proves local improvement, not coherent seam closure.

### False Closure 3: Broad API Cleanup Mistaken For Seam Closure

- endpoint shapes become cleaner or more uniform
- but the receipt-linked inspectability contract is still not explicitly closed

This proves API cleanup, not the selected maturity seam.

### False Closure 4: Tool-Catalog Or Bundle/Export Evidence Miscounted

- tool-catalog queries improve
- or bundle/export proof works better
- but receipt-linked inspectability/query coherence is not closed

This is supporting-surface progress, not selected seam closure.

### False Closure 5: Minimum Path Regresses While Broader Query Improves

- a broader query surface appears stronger
- but receipt retrieval, replay linkage, or receipt-linked continuity regresses

This fails acceptance because seam closure is downstream of preserved baseline continuity.

## Exact Acceptance Standard

The selected broader GovMCP maturity seam is closed only if all of the following are satisfied:

1. There is an explicit canonical inspectability/query contract for the selected receipt-linked state.
2. Receipt, replay, and tool-event linkage surfaces materially conform to that contract.
3. The already-landed minimum path remains intact and evidenced.
4. Any exposure-layer changes are narrow, seam-specific, and downstream of the closed contract.
5. At least one false-closure pattern is explicitly tested or demonstrated as rejected.
6. Closure cannot be satisfied solely by tool-catalog health, bundle/export health, broad API cleanup, or DevCore workflow maturity.

If any one of those conditions is missing, the seam should remain open.

## Evidence Strength Expectations

The strongest evidence package would include:

- bounded contract/spec language
- targeted automated tests for cross-surface consistency
- targeted regression tests proving minimum-path preservation
- one explicit anti-inflation test

Weaker evidence packages may be useful during development, but they should not be treated as sufficient for claiming the seam is closed.

## Decision Summary

- Closure proof must be seam-specific, not generic GovMCP maturity proof.
- Minimum-path preservation is mandatory, not optional.
- Anti-inflation proof is mandatory because the most likely failure mode is overcounting adjacent or baseline health as broader seam closure.
