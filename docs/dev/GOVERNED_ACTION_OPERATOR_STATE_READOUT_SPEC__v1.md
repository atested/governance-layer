# Governed Action Operator State / Readout Specification v1

**Status:** Cecil-authored design materialized as repo canon for the bounded v1 readout tranche.  
**Objective:** Define the minimum operator-facing readout layer required to make the governed-action runtime legible without reopening the governed-action substrate or adding new control surfaces.

## Problem statement

The governed-action substrate now includes decision recording, opaque-path handling, approval state, verification state, and opacity metrics. That substrate is sufficient for enforcement and replay, but it is not yet sufficient for direct operator readout.

Without a bounded readout layer, the operator must reconstruct current governance posture by inspecting multiple runtime and chain surfaces separately. That is too indirect for the next baseline step. The missing layer is not more governance substrate. The missing layer is a minimal, read-only operator-facing assembly of the substrate that already exists.

## Why the current governed-action substrate was insufficient without readout

The substrate already records the necessary facts, but those facts are distributed across:

- runtime approval state
- runtime verification state
- chain events describing approval, revocation, verification transitions, and opaque-path handling
- opacity metrics derived from the decision chain
- chain integrity and reconstruction checks

That substrate answers "what happened" and "what state exists," but it does not directly answer the operator question "what is the current governed-action state right now?" A bounded operator-facing readout layer is therefore required to project the current state into one coherent point-in-time object.

## Canonical object model

The canonical operator-facing object for this tranche is the **Governed Action Status Record (GASR)**.

GASR is:

- projected
- read-only
- a point-in-time snapshot
- assembled from runtime singletons and chain data
- not persisted
- not a chain event

GASR is not a new authority surface. It is a readout assembly over already-landed authority surfaces.

## Surfaced dimensions

GASR must surface exactly these six dimensions:

1. transparency / opacity posture
2. approval state
3. verification state
4. drift status
5. chain integrity / reconstruction status
6. runtime outcome summary

These dimensions are sufficient for the bounded v1 operator readout layer. No additional operator-state dimensions are required for this tranche.

## Evidence model

Every surfaced GASR dimension must trace to specific chain events or runtime state entries.

The evidence model for v1 is:

- transparency / opacity posture traces to the decision chain and baseline opacity-metrics derivation
- approval state traces to the active approval runtime state reconstructed from approval and revocation events
- verification state traces to the active verification runtime state reconstructed from verification-state transition events
- drift status traces to verification-state entries indicating drift-detected state
- chain integrity / reconstruction status traces to chain verification and reconstruction checks against current runtime state
- runtime outcome summary traces to recorded opaque-path and related runtime outcome entries already present in the governed-action substrate

The readout layer must not introduce:

- derived scores
- composite indices
- health scoring
- synthetic rollups that are not directly evidence-backed

## Control model

The v1 operator readout layer is read-only.

Mutation continues through existing governance control paths only, including already-landed tools such as:

- `approve_artifact`
- `revoke_artifact`
- `certify_surface`
- related existing governed-action mutation paths

v1 does not add any new control surfaces. GASR does not mutate state, does not authorize actions, and does not replace the existing governance mutation surfaces.

## Minimum views

v1 defines exactly three operator-facing views:

1. `governance_status`
2. `governance_approvals`
3. `governance_verification`

These views are the minimum bounded readout surface for v1.

### `governance_status`

This is the top-level GASR projection. It must surface the bounded current operator-facing governance state by assembling the required six dimensions from runtime singletons and chain data.

### `governance_approvals`

This is the focused approval readout view. It surfaces current approval state only. It remains read-only and does not replace approval mutation tools.

### `governance_verification`

This is the focused verification readout view. It surfaces current verification and drift state only. It remains read-only and does not replace verification mutation tools.

No additional views are required in v1.

## In-scope surfaces

The bounded v1 implementation path is:

- one assembly module
- three MCP tools
- chain integrity check
- opacity metrics integration
- tests

This path is already judged bounded. No further design work is required to execute v1 within these limits.

## Out-of-scope surfaces

The following are explicitly out of scope for v1:

- historical queries
- compound display
- push alerts
- metric trending
- operator identity gating
- health scores
- case grouping
- visual rendering / UI

Also out of scope:

- new mutation/control tools
- broader dashboard frameworks
- reopening governed-action substrate architecture

## Acceptance-proof concept

The acceptance proof for this design is implementation-level and bounded.

v1 is proven landed when:

- the GASR assembly module exists
- `governance_status` exists
- `governance_approvals` exists
- `governance_verification` exists
- all six required dimensions are surfaced from real runtime and chain sources
- the readout layer remains read-only
- no new mutation surface is introduced
- bounded tests verify readout shape, source-backed fields, and fail-closed or missing-data behavior where required

This is a proof of bounded operator readout materialization, not a redesign of the governed-action runtime.

## Exact recommended next control step as it existed at design time

The recommended next control step at design time was:

Implement the bounded GASR/operator-readout tranche exactly as a read-only assembly layer over the already-landed governed-action substrate, using one assembly module, three MCP views, chain integrity and reconstruction status, opacity metrics integration, and bounded tests, with no new mutation surfaces and no further substrate invention.
