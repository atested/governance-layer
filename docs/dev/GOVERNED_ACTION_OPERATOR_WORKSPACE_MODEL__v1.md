# Governed Action Operator Workspace Model v1

**Status:** Cecil-authored design materialized as repo canon for the governed-action operator v1 workspace layer.  
**Objective:** Define the minimum workspace model that makes the existing governed-action operator surfaces navigable as one coherent operator-facing system without adding new governance substrate, new runtime state, or UI design commitments.

## Problem statement

The governed-action operator now faces ten independent MCP tools. Those tools exist, but there is no canonical statement of how they relate to one another, which surface is the universal starting point, or how the operator is expected to navigate from readout to action.

The missing value is navigation coherence.

This is not a missing governance primitive. It is not a missing runtime subsystem. The gap is that the operator-facing architecture is not yet defined as a workspace model.

## Why current projections and controls were insufficient by themselves

The current governed-action operator surface consists of:

- read-only projections
- mutation/control tools

Those surfaces are individually useful, but they do not by themselves define:

- the universal entry point
- the expected relationship between state, activity, detail, and controls
- the navigation contract from observation to action
- the shared identifiers that make cross-surface movement coherent

Without that model, the operator has tools but not a canonically defined workspace.

## Canonical workspace model

The canonical v1 workspace model is a navigation model over existing governed-action surfaces.

It is defined by:

- one universal entry point
- condition-driven navigation paths from status to detail/activity surfaces
- evidence-driven navigation paths from activity to controls
- cross-reference linkage through shared identifiers already present in the governed-action system

The workspace model is organizational, not stateful. It does not add a new governance object, new persisted operator session, new chain structure, or new mutation surface.

## Primary entry point

The universal starting point for the v1 operator workspace is:

- `governance_status`

`governance_status` is the entry point because it provides the current governed-action snapshot and is therefore the surface from which the operator can identify whether the system is nominal or non-nominal before deciding where to go next.

## Navigation model

The navigation model is bounded and condition-driven.

### From Status to detail or activity surfaces

The operator begins at `governance_status`, identifies a non-nominal condition or notable condition, and then follows documented navigation paths to the relevant supporting surface:

- from status to `governance_activity` when recent sequence or progression legibility is needed
- from status to approvals detail when the condition concerns approval state
- from status to verification detail when the condition concerns verification state or drift

This is condition-driven navigation: the current state determines which supporting surface is relevant.

### From Activity to controls

The operator uses `governance_activity` when the recent event sequence is needed to understand how the current state arose. From activity entries, navigation to controls is evidence-driven, not guess-driven.

The operator follows evidence already present in the surfaces:

- `event_id`
- `artifact_identity`
- `governed_family`

These identifiers connect recent activity to the relevant detail view or control path without introducing a new navigation state machine.

### Cross-reference linkage

The workspace model depends on shared identifiers across surfaces:

- `event_id`
- `artifact_identity`
- `governed_family`

These shared identifiers provide the navigation contract. They make it possible to move from:

- status to the relevant detail surface
- activity to the relevant control
- detail back to the related progression evidence

without creating new surfaces or new data structures.

## Evidence/support relationship between surfaces

The v1 workspace separates observation from action while keeping them linked.

The read-only projection surfaces support operator understanding:

- current status
- recent activity
- approval detail
- verification detail

The control surfaces perform mutation:

- approval mutation
- revocation
- verification certification / drift reporting / recertification
- related existing control actions

The supporting relationship is:

- projections tell the operator what exists and what happened
- controls let the operator act
- shared identifiers connect the two

The workspace model therefore organizes the existing governed-action operator surfaces into one evidence-supported operator flow without adding any new substrate.

## In-scope surfaces

The minimum v1 workspace composition is:

- entry point:
  - `governance_status`
- activity:
  - `governance_activity`
- two detail surfaces:
  - approvals detail
  - verification detail
- six controls:
  - the existing mutation/control surfaces already landed for approval and verification handling
- cross-reference linkage through shared identifiers

This yields:

- 4 projection surfaces (read-only)
- 6 control surfaces (mutation)

That is the complete bounded v1 workspace model.

## Out-of-scope surfaces

The following remain explicitly out of scope for v1:

- UI layout or visual design
- navigation enforcement or navigation state machine behavior
- session state or operator context persistence
- role-based access or view gating
- composite or merged views
- historical state reconstruction
- compound action grouping
- push notifications
- case-based grouping

Also out of scope:

- workflow-engine behavior
- new runtime state
- new chain structures
- new governance substrate

## Acceptance-proof concept

The workspace model is proven sufficient at v1 when an operator can:

1. start at `governance_status`
2. identify non-nominal conditions
3. follow documented navigation paths to the relevant detail or activity surface using existing identifiers
4. reach the relevant control tool for action
5. do so without any new surfaces, new state, or new chain structures

This is a proof of workspace coherence, not a proof of UI design or workflow automation.

## Exact recommended next control step as it existed at design time

The exact recommended next control step at design time was:

- Path A: no implementation needed; the workspace model is complete as a design document organizing existing tools
- Path B: an optional `governance_workspace` tool only if MCP client integration later requires it

The v1 recommendation was Path A. The workspace model is sufficient as a design document organizing the existing projections, controls, and identifier-based navigation paths without requiring a new runtime surface.
