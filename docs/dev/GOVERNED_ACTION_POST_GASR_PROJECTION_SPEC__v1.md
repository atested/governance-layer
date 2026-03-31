# Governed Action Post-GASR Projection Specification v1

**Status:** Cecil-authored design materialized as repo canon for the bounded post-GASR activity-projection tranche.  
**Objective:** Define the minimum operator-facing recent-activity projection above GASR v1 without reopening governed-action substrate architecture or broadening the operator model.

## Problem statement

GASR v1 answers the operator question: "What is the current governed-action state right now?"

It does not answer the next operator question: "What sequence of governance events produced this state?"

The missing value is not historical state reconstruction. The missing value is recent activity legibility: a bounded, structured, evidence-linked view of recent governance-significant events so the operator can interpret the current snapshot without parsing raw chain JSONL.

## Why GASR v1 was insufficient by itself

GASR v1 gives current-state views:

- `governance_status`
- `governance_approvals`
- `governance_verification`

Those views show current posture, current approvals, and current verification state. They do not directly show the recent sequence that produced the present state. An operator can see that a surface is in drift, or that an approval is active, but not the bounded recent progression around those facts. A post-GASR activity projection is therefore required to make recent governed-action progression legible without broadening GASR into a history surface.

## Canonical projection definition

The canonical post-GASR projection for this tranche is `governance_activity`.

`governance_activity` is:

- read-only
- projected
- filtered
- paginated
- evidence-linked
- assembled from recent chain events
- not persisted
- not a chain event

It is a bounded operator-facing view over recent governance-significant chain records. It is not a new state surface and it does not mutate governance runtime state.

## Distinction from GASR views

The distinction is strict:

- GASR = current snapshot
- `governance_activity` = recent progression / sequence legibility

GASR answers the current-state question. `governance_activity` answers the recent-sequence question. The activity projection does not replace GASR, duplicate GASR, or reconstruct point-in-time historical state. It provides the bounded recent event context that GASR intentionally omits.

## Minimum projection contents

The bounded v1 projection normalizes exactly these five current event categories:

1. `action_decision`
2. `verification_transition`
3. `opaque_approval`
4. `opaque_revocation`
5. `opaque_invocation_decision`

Each activity entry must include:

- normalized `event_category`
- bounded summary string
- category-specific detail fields
- per-entry evidence links:
  - `event_id` or `request_id` as applicable
  - `record_hash`
- any bounded cross-reference fields required to relate the entry back to the authoritative chain record

The projection is recent-window based and operator-facing. It is not a full raw-chain dump.

## Control model

The bounded controls for `governance_activity` are:

- window controls:
  - `limit`
  - `offset`
- filter controls:
  - `governed_family`
  - `event_category`
  - `resolution`

These controls exist only to bound and filter the projection. They do not mutate state, alter the chain, or add historical reconstruction semantics.

No additional controls are required for v1.

## Evidence-link model

Every activity entry must link back to the authoritative chain evidence.

The minimum evidence-link model is:

- non-action events surface `event_id` and `record_hash`
- action records surface `request_id` and `record_hash`

This keeps the projection grounded in specific chain records rather than derived summaries without evidence. Cross-reference linkage to GASR identifiers must remain intact where shared identifiers already exist, so an operator can correlate current-state readouts with recent-activity entries without introducing a new linking system.

## In-scope surfaces

The bounded v1 implementation path is:

- one new MCP tool: `governance_activity`
- chain-reading projection logic in the readout module
- entry normalization for the five current event categories
- window controls: `limit`, `offset`
- filter controls: `governed_family`, `event_category`, `resolution`
- per-entry evidence links
- bounded tests

No substrate changes are required for this tranche.

## Out-of-scope surfaces

The following remain explicitly out of scope for v1:

- historical state reconstruction
- compound action grouping
- event search by content
- push notifications / streaming
- visual rendering / UI
- event annotation or tagging
- cross-chain aggregation
- metric derivation

Also out of scope:

- new mutation/control behavior
- runtime substrate changes
- redesign of existing GASR views

## Acceptance-proof concept

The post-GASR activity projection is proven landed when:

- `governance_activity` exists
- entries are correctly normalized for all five event categories
- evidence fields are present
- summary derivation is present
- window and filter controls work as defined
- empty-chain safety holds
- the read-only invariant holds
- cross-reference linkage to GASR view identifiers is preserved where applicable
- bounded test coverage exists

This is a proof of bounded operator-facing activity legibility, not a redesign of the governed-action runtime or a move into historical state reconstruction.

## Exact recommended next control step as it existed at design time

The exact recommended next control step at design time was:

Implement one bounded MCP tool, `governance_activity`, backed by chain-reading logic in the readout module, with normalization for the five current event categories, window and filter controls, per-entry evidence links, and bounded tests, with no substrate changes needed.
