# Design UI Workspace v1 Design

Task: DESIGN-WS-001
Status: Design handoff

## 1. Purpose

This document defines the product design for converting Design UI from a page-oriented local application into a workspace-oriented design environment.

The goal is not to design a perfect final IDE. The goal is to define a coherent v1 workspace model that preserves the existing Design UI architecture while giving the operator enough room and control to stay in flow during design work.

## 2. Design Problem

Design UI v1 works architecturally:

```text
chat/manual input
-> proposal
-> operator approval
-> committed Discovery/Purpose/Relationship state
-> lineage
-> map/context
-> specification builder
-> validation/export
```

The ergonomic problem is that the current interface is still organized as fixed pages:

- `/design` holds Discovery, Purpose, Chat, Proposals, and Lineage in a fixed layout.
- `/map` is a separate orientation page.
- `/spec` is a separate builder/export page with validation.
- Lineage is always present in `/design`, even when it is not the operator's current focus.
- Chat, Discovery, and Purpose compete for vertical and horizontal room.
- The current token system is readable but visually dominated by neutral gray surfaces.

This makes the product feel like a set of pages rather than a working room where the operator can arrange surfaces around the task.

## 3. Operator Workflow Goal

The operator should be able to open `/design` and remain in a single workspace for the normal design loop:

1. Talk through a design problem in Chat.
2. Capture or review Discovery observations.
3. Promote, demote, and refine Purpose candidates.
4. Review pending Proposals without leaving the work surface.
5. Keep a Map nearby for orientation and active context.
6. Pull Lineage, Validation, and Spec forward when needed.
7. Reset the workspace if the layout gets noisy.

The workspace should support arrangement without requiring configuration before first use.

## 4. Workspace Principles

1. The workspace is the primary product surface.
2. Chat, Discovery, and Purpose are the main working triangle.
3. Proposals are the commit gate and must stay visible or one click away.
4. Map is an orientation surface, not the main editor.
5. Lineage, Validation, and Spec are support surfaces until the operator explicitly brings them forward.
6. Docking and tabbing are layout affordances only; they must not change state authority or approval semantics.
7. Popout windows are useful for focused review, but v1 should not depend on multi-window behavior for correctness.
8. The visual system should remain restrained and operational while adding enough hierarchy to reduce gray fatigue.

## 5. Surface Taxonomy

| Surface | Classification | Role in workspace | Default treatment |
| --- | --- | --- | --- |
| Chat | Primary work surface | Operator conversation, stub proposal creation, design thinking capture | Large primary panel |
| Discovery | Primary work surface | Observations, questions, anomalies, raw material | Large primary panel with Discovery accent |
| Purpose | Primary work surface | Purpose candidates, constraints, boundaries, operational intent | Large primary panel with Purpose accent |
| Proposals | Secondary support surface and commit gate | Pending proposal review, accept/reject controls, provenance preview | Visible support panel or docked tab near primary surfaces |
| Map | Secondary support surface | Orientation, active-context selection, relationship overview | Smaller docked panel, available by default |
| Lineage | Inspection/audit surface | Playback of committed changes, proposal/message references | Tabbed with Validation/Spec by default |
| Validation | Inspection/audit surface | Advisory checks and remediation signals | Tabbed support panel, not dominant |
| Spec | Output/export surface | Preview, section review, persisted export | Tabbed support panel, not dominant |

## 6. Default Workspace Layout

Recommended first-launch layout:

```text
+--------------------------------------------------------------------------+
| Workspace toolbar: project, context, pending count, reset layout, theme  |
+--------------------------+--------------------------+-------------------+
| Chat                     | Discovery                | Purpose           |
| 35% width                | 32.5% width              | 32.5% width       |
| primary height           | primary height           | primary height    |
+-----------------------------------------+--------------------------------+
| Map                                     | Proposals                      |
| support height                          | support/commit gate            |
+-----------------------------------------+--------------------------------+
| Tab strip: Lineage | Validation | Spec                                    |
+--------------------------------------------------------------------------+
```

Behavior:

- Chat gets enough width and height for real interaction.
- Discovery and Purpose are equally visible by default to preserve the distinction.
- Map is visible but smaller so active context remains available without taking over.
- Proposals are visible by default because approval is the system boundary.
- Lineage, Validation, and Spec are tabbed in a lower or side support region.
- On narrower screens, the default can collapse into stacked tab groups, but all required surfaces remain registered.

## 7. Docking and Tabbing Model

All eight required surfaces should be registered as workspace panels:

- `chat`
- `discovery`
- `purpose`
- `proposals`
- `map`
- `lineage`
- `validation`
- `spec`

Dockable in v1:

- all panels should be dockable and resizable;
- primary panels should be allowed in the main grid;
- support panels should be allowed in side, bottom, or tabbed regions.

Recommended tab groupings:

- `discovery` and `purpose` may be tabbed together only if the operator chooses; they should not default to the same tabset because both must be visible on first launch.
- `lineage`, `validation`, and `spec` should default to one support tabset.
- `map` and `proposals` may be tabbed together in compact layouts, but desktop default should show both.
- `chat` should be dockable but should not default into a hidden tab because it anchors the operator flow.

The workspace shell should expose simple commands:

- reset layout;
- open panel if closed;
- focus panel;
- pop out supported panels where the selected library supports it.

## 8. Popout Window Model

Popout is desirable but should be pragmatic in v1.

Recommended v1 popout support:

- Support popout for `map`, `spec`, `validation`, and `lineage` first.
- Support popout for `chat`, `discovery`, `purpose`, and `proposals` only if the selected library makes it low-risk.
- Treat popped-out panels as alternate views over the same project state, not separate state owners.
- Keep approval actions valid only through the same API and proposal committer path.
- Refresh popped-out panels from the same project-scoped API state.

Multi-window behavior:

- Layout state may remember that a panel was popped out if the library serializes it cleanly.
- If restoring a popout fails because the browser blocks or closes the child window, restore that panel docked in its default support group.
- Closing a popout should not delete the panel; it should return to the panel menu or be restorable through reset.

Popout should not be required for acceptance. Docking and tabbing are the core v1 requirement; popout can be limited to library-supported behavior.

## 9. Layout Persistence Model

Persist workspace layout locally in `localStorage`.

Recommended key:

```text
design-ui:workspace-layout:v1:{projectId}
```

Rules:

- Layouts should be project-specific in v1 because active context and operator intent are project-scoped.
- If `projectId` is not known yet, use the default layout until the project loads, then restore project-specific layout.
- Store only layout metadata, not Discovery/Purpose/Proposal content.
- Use the docking library's serialization format if available.
- Include a layout schema version so future migrations can discard incompatible v1 layouts cleanly.
- Reset layout deletes the project-specific key and rehydrates the default layout.

The existing theme key, `design-ui:theme`, must remain unchanged.

## 10. Visual Direction

Current Design UI tokens already preserve light/dark/system behavior and avoid pure black in dark mode. Keep that foundation.

Visual changes for workspace v1:

- Reduce flat gray dominance by adding surface roles, not decoration.
- Keep the dark background in the `#1a1d23` family, aligned with the current Design UI and Atested operator UI.
- Use raised surfaces sparingly for active panels, selected tabs, and proposal cards.
- Use thin borders and modest contrast shifts rather than heavy shadows.
- Keep radius at 6-8px for Design UI unless adopting the sharper Atested operator UI token language proves better in implementation.

Discovery and Purpose differentiation:

- Discovery should use a cool observation accent, such as blue/cyan, for panel stripe, tab indicator, empty state, and item metadata.
- Purpose should use a distinct intent accent, such as green/teal, for panel stripe, tab indicator, empty state, and item metadata.
- Proposals should use amber only for pending/attention states, not as general decoration.
- Validation should reuse success/warning/error semantics already present in the token system.
- Map can use the existing blue accent for connected nodes and a softer purple/indigo only for relationship or concept grouping if needed.

Influence from Atested/current web UI:

- Favor dense, operational surfaces with clear evidence/provenance hierarchy.
- Prefer explicit status and source labels over decorative imagery.
- Preserve the governance product's bias toward deterministic boundaries and visible confidence.
- Use accent color to communicate type, status, and source; do not use color as a general background wash.

## 11. MCP/Codex Interaction Model

MCP behavior must remain unchanged:

- MCP clients may read committed state.
- MCP clients may create pending proposals.
- MCP clients may not approve, reject, or directly mutate committed state.
- Operator approval in Design UI remains the only path to committed-state mutation.

Workspace treatment:

- MCP-created proposals appear in the same Proposals panel as local/manual/stub proposals.
- MCP proposals should show a source badge derived from `proposedChanges.metadata.mcp`, such as `Codex`, `MCP`, model name, or request id when available.
- Local/manual proposals should show a separate `Manual` or `Design UI` source label.
- Proposal cards should preserve the current preview structure: creates, changes, connections, and lineage events.
- The Proposals panel should support filtering by status and source in a later iteration, but v1 only needs clear source display.
- Codex may appear as a participant/source in proposal provenance, but not as an approver.

The UI copy and interaction model should reinforce that approval is an operator action, not an AI action.

## 12. Library Evaluation

Metadata checked during this design task:

- `golden-layout` version `2.6.0`, MIT, package modified `2023-02-21`.
- `dockview` version `6.6.1`, MIT, package modified `2026-05-26`, React peer dependency includes React 19.
- `flexlayout-react` version `0.9.1`, ISC, package modified `2026-05-04`, React and React DOM peer dependencies include React 19.

| Library | React/Vite fit | Docking | Tabbing | Popout | Persistence | Maintenance risk | Complexity | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Golden Layout | Works with modern bundlers but is not React-first; React integration requires adapter work | Strong classic docking model | Strong | Native popup windows are a known strength | Load/save layouts supported | Higher: npm package has not been modified recently compared with alternatives | Medium-high because Design UI is React 19 and would need careful wrapping | Do not choose for v1 despite conceptual fit; keep as fallback if popout becomes the overriding requirement |
| Dockview | Strong fit; package is React-oriented and supports React 19 | Strong dockable panels, groups, grids, split views, floating groups | Strong tab/group model | Supports popout windows and floating panels | Serialization/deserialization supported | Low relative risk based on current package activity and React 19 peer support | Medium; richer API but aligned with the desired workspace | Recommended |
| FlexLayout | Strong React fit with React 19 support | Strong docking to tabsets and frame edges | Strong tabset model | Supports floating panels and browser-window popouts | Model serializes to/from JSON | Low-medium; active enough, mature model, but less directly "workspace IDE" oriented than Dockview | Medium; JSON model is straightforward, styling may need more adaptation | Acceptable fallback if Dockview integration proves heavier than expected |

Other libraries were not selected because the three above cover the practical decision space: classic Golden Layout style, modern React docking, and JSON-model React tabsets.

## 13. Recommended Library

Recommend `dockview` for workspace v1.

Reasons:

- It is React-compatible with the current React 19 app.
- It supports dockable panels, tab groups, grids, split views, floating panels, and popout windows.
- It supports layout serialization/deserialization, which fits local persistence.
- Its package metadata indicates active maintenance.
- It maps cleanly to registering Design UI surfaces as panel components.

Golden Layout remains the conceptual reference for the desired interaction style, especially popout behavior, but Dockview is the better practical fit for this repo.

FlexLayout is the fallback if Dockview's API or styling proves too heavy during implementation. Its model JSON could be easier to test, but Dockview better matches the requested workspace/product feel.

## 14. Recommended v1 Scope

Workspace v1 should include:

- `/design` becomes the workspace itself.
- Existing `/map` and `/spec` routes remain as direct deep links and compatibility surfaces.
- A workspace shell with a toolbar, panel registry, reset layout control, project/status indicators, and theme picker.
- Dockview-backed panels for Chat, Discovery, Purpose, Proposals, Map, Lineage, Validation, and Spec.
- Default layout matching the primary/support taxonomy above.
- Local project-specific layout persistence.
- Reset-to-default.
- Source badges for MCP-created proposals.
- Visual differentiation for Discovery and Purpose.
- Preservation of existing APIs, proposal acceptance/rejection, MCP tools, and theme behavior.

Implementation should extract the existing route sections into reusable panel components rather than rewriting business logic.

## 15. Deferred Scope

Defer:

- Real AI extraction behavior.
- Multi-project layout management beyond project-specific localStorage.
- Shared/collaborative workspace layouts.
- Server-side layout persistence.
- Advanced graph visualization or force-directed Map layout.
- Rich Lineage playback/timeline controls.
- Spec editor semantics beyond current preview/export behavior.
- Full multi-monitor window orchestration if the chosen library's popout support is insufficient.
- User-defined saved layout presets beyond default/reset.
- Proposal diff sophistication beyond current preview shape.

## 16. Spec Cycle Handoff Notes

The formal spec cycle should define:

- The exact panel registry type and panel ids.
- The default Dockview layout object.
- The localStorage schema and migration/reset behavior.
- Which existing route components must be extracted into shared panel components.
- The Proposals source badge mapping for `metadata.mcp`.
- The panel refresh strategy after proposal accept/reject and MCP-created proposals.
- Tests for panel registration, default layout presence, layout reset, and proposal/MCP semantics.
- Compatibility behavior for `/map` and `/spec`.
- Theme token additions for workspace surfaces, Discovery accent, Purpose accent, source badges, and docking chrome.

Recommended implementation sequence:

1. Add workspace panel registry and default layout model.
2. Extract existing route sections into reusable panel components.
3. Introduce Dockview shell on `/design`.
4. Add layout persistence and reset.
5. Add source badges and visual hierarchy refinements.
6. Add focused tests.
7. Run `npm test`, `npm run typecheck`, and `npm run build`.

## 17. Open Questions

1. Should `/map` and `/spec` remain visually independent routes long term, or become thin redirects into focused workspace layouts?
2. Should layout persistence be per project only, or should there also be a global fallback layout after project selection exists?
3. Should Proposals always remain visible by default, or is a prominent pending-count tab sufficient on smaller screens?
4. Should MCP source labels expose model/client session details by default, or hide those behind a details disclosure?
5. Should popout support be limited to inspection/output panels in v1 to reduce multi-window state risk?
6. Should the workspace eventually support named layout presets such as `Capture`, `Map Review`, and `Spec Handoff`?
