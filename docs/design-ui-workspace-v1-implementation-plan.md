# Design UI Workspace v1 Implementation Plan

Task: DESIGN-WS-PLAN-001
Status: Implementation planning handoff
Inputs:

- Approved design: `docs/design-ui-workspace-v1-design.md`
- Approved review: DESIGN-WS-REVIEW-001, `APPROVED_FOR_SPEC`

## 1. Purpose

This document decomposes Workspace v1 into bounded implementation batches suitable for future Codex dispatches.

The plan preserves the approved design direction: `/design` becomes the workspace itself, Chat/Discovery/Purpose are primary work surfaces, Proposals and Map are visible support surfaces, and Lineage/Validation/Spec are secondary tabbed surfaces. It also resolves the approved review notes before implementation starts.

This is a planning artifact only. It does not implement code, add dependencies, or change runtime behavior.

## 2. Assumptions

1. `origin/main` contains the current Design UI v1 app, MCP implementation, dark/light/system theme support, launcher scripts, and existing tests.
2. The approved workspace design is authoritative even if its document lands on a separate branch before this plan is merged.
3. `dockview` remains the recommended library for implementation, but it should not enter the codebase until existing panels have been extracted and verified.
4. Existing API, proposal, MCP, map, lineage, validation, spec, and theme semantics must remain unchanged.
5. Existing `/map` and `/spec` routes remain available through Workspace v1.
6. Runtime state mutation remains approval-gated through Design UI; MCP clients remain proposal-only for writes.

Review note closures:

- Narrow proposal visibility: desktop default keeps Proposals visible; compact/narrow layouts must keep a visible Proposals tab or fixed workspace command with pending count. Proposals must not be reachable only through hidden overflow.
- Theme tokens: Workspace v1 token names and initial color assignments are locked in the Theme Plan below.
- Panel extraction: panel extraction is intentionally scheduled before Dockview in Batches 1-3.
- Popout scope: v1 popout is limited to support/inspection/output panels first; primary panel popout is deferred unless Dockview makes it low-risk.

## 3. Migration Strategy

Use a staged migration that keeps the current pages working while extracting reusable panel units.

Stage 1: panel extraction without Dockview.

- Extract current `/design` subsections into panel components, but keep `DesignRoute` rendering the same fixed layout.
- Extract Map and Spec internals into panel-compatible components, but keep `/map` and `/spec` rendering unchanged.
- Keep all current API calls and state ownership at route level until component boundaries are stable.
- Update tests to verify equivalent rendered markers and behavior.

Stage 2: workspace shell without changing committed-state behavior.

- Introduce a workspace-level project data controller that owns the shared project id and refresh function.
- Register the eight panels by stable id: `chat`, `discovery`, `purpose`, `proposals`, `map`, `lineage`, `validation`, `spec`.
- Initially render the registry through a simple static workspace harness if needed.
- Do not add Dockview until the panel registry and state controller are testable.

Stage 3: Dockview integration.

- Add Dockview dependency in its own implementation batch.
- Replace the static workspace harness with Dockview panel rendering.
- Load the default layout only after the project id and panel registry are available.
- Keep `/map` and `/spec` as route surfaces backed by the same extracted components.

Stage 4: workspace behavior hardening.

- Add project-specific layout persistence.
- Add reset-to-default.
- Add visual hierarchy tokens.
- Add proposal source badges.
- Add limited popout behavior only where Dockview supports it cleanly.

This sequence avoids a high-risk rewrite where panel extraction, dependency introduction, layout persistence, and visual redesign all land together.

## 4. Batch Breakdown

### Batch 1: Panel Extraction Foundation

Purpose:

- Prove existing surfaces can become reusable panels before Dockview enters.

Expected changes:

- Create panel component boundaries for Chat, Discovery, Purpose, Proposals, and Lineage.
- Keep `DesignRoute` visually and behaviorally equivalent.
- Keep existing test ids stable where possible.
- Add panel metadata types or constants without using a docking library.

Risks:

- Props may become too broad if route state is lifted poorly.
- Proposal accept/reject refresh behavior can regress during extraction.

Dependencies:

- None beyond current app.

Verification requirements:

- `npm test`
- `npm run typecheck`
- Existing proposal flow tests unchanged or expanded.
- Static route structure tests still prove Discovery, Purpose, Proposal approval controls, active context, and Lineage exist.

### Batch 2: Map, Spec, and Validation Panel Extraction

Purpose:

- Make secondary and output surfaces reusable in both routes and workspace panels.

Expected changes:

- Extract Map content into a `MapPanel`-style component.
- Extract Spec preview/export content into a `SpecPanel`-style component.
- Extract Validation display into a standalone `ValidationPanel`-style component usable by Spec and workspace.
- Keep `/map` and `/spec` routes behaviorally unchanged.

Risks:

- Spec route currently couples preview, validation, sections, and export list.
- Map route currently owns node selection and navigation back to `/design`.

Dependencies:

- Batch 1 panel conventions.

Verification requirements:

- `npm test`
- `npm run typecheck`
- Tests confirm `/map` still has filters, node grid, edge list, and context selection.
- Tests confirm `/spec` still has preview, validation, export, and required sections.

### Batch 3: Workspace State Controller and Panel Registry

Purpose:

- Centralize shared project state for all panels without changing UI layout yet.

Expected changes:

- Add a workspace controller/hook that loads the active project and shared data.
- Define the panel registry with all eight required ids.
- Define panel display names, default importance, and allowed panel capabilities.
- Render through the current route or a static workspace harness to prove the contract.

Risks:

- Loading all panel data at once may create avoidable API calls.
- Refresh needs to update all surfaces after accept/reject without losing draft input unexpectedly.

Dependencies:

- Batches 1 and 2.

Verification requirements:

- `npm test`
- `npm run typecheck`
- New tests for panel registry completeness.
- New tests for default required panels: Chat, Discovery, Purpose, Proposals, Map, Lineage, Validation, Spec.

### Batch 4: Dockview Shell and Default Layout

Purpose:

- Introduce the docking workspace and make `/design` the workspace itself.

Expected changes:

- Add Dockview dependency.
- Add `WorkspaceRoute` or convert `DesignRoute` into the Dockview workspace shell.
- Register all extracted panels as Dockview panel components.
- Add the approved default layout:
  - Chat, Discovery, Purpose as primary panels.
  - Map and Proposals visible as support panels.
  - Lineage, Validation, Spec in one secondary tab group.
- Keep `/map` and `/spec` direct routes.

Risks:

- Dockview CSS may conflict with current token rules.
- Panel lifecycle may remount components and reset local drafts.
- Narrow-screen layout behavior may require specific Dockview configuration.

Dependencies:

- Batches 1-3.

Verification requirements:

- `npm test`
- `npm run typecheck`
- `npm run build`
- New tests for default layout presence.
- Manual browser check of `/design`, `/map`, `/spec`.

### Batch 5: Layout Persistence and Reset

Purpose:

- Persist operator workspace arrangement locally and provide a clean recovery path.

Expected changes:

- Add project-specific localStorage persistence.
- Add layout schema version.
- Add reset layout command.
- Add corrupted/unknown-version fallback to default layout.

Risks:

- Persisted layouts can restore stale panel ids after future changes.
- Bad localStorage data can blank the workspace if fallback is weak.

Dependencies:

- Batch 4.

Verification requirements:

- `npm test`
- `npm run typecheck`
- Tests for storage key format, default fallback, reset behavior, and version mismatch.
- Manual browser check: rearrange, reload, reset, reload again.

### Batch 6: Theme Tokens and Workspace Visual Hierarchy

Purpose:

- Reduce flat gray dominance while preserving dark/light/system behavior.

Expected changes:

- Add workspace-specific token names and use them through CSS variables only.
- Add Discovery/Purpose accent treatment.
- Add restrained proposal, MCP source, and support-surface styling.
- Style Dockview chrome to match Design UI tokens.

Risks:

- Raw colors can accidentally enter component CSS and break theme tests.
- Dockview theme CSS can overpower app tokens.
- Too much accent use can make the workspace visually noisy.

Dependencies:

- Batch 4 can precede this; Batch 5 can run before or after.

Verification requirements:

- `npm test`
- `npm run typecheck`
- Theme tests updated to include new tokens.
- Visual check in light, dark, and system modes.

### Batch 7: MCP Proposal Source and Narrow-Screen Behavior

Purpose:

- Close review notes around proposal visibility and MCP/Codex source treatment.

Expected changes:

- Add proposal source badge mapping:
  - `MCP` / `Codex` from `proposedChanges.metadata.mcp`.
  - `Manual` or `Design UI` for local proposals.
- Ensure narrow screens keep Proposals reachable through a visible tab or fixed workspace command.
- Confirm approval controls remain operator-only.
- Add limited popout capability for support panels if Dockview integration is stable.

Risks:

- Badge parsing can assume metadata shape too strongly.
- Narrow layout can hide the commit gate if Proposals are only in an overflow menu.
- Popout windows can create confusing refresh behavior.

Dependencies:

- Batch 4.
- Batch 5 if popout state is persisted.

Verification requirements:

- `npm test`
- `npm run typecheck`
- `npm run build`
- Tests for MCP badge rendering from metadata.
- Tests or documented manual check that narrow-screen Proposals remain visible/recoverable.
- Manual check that accept/reject still calls only existing UI/API paths.

## 5. Panel Extraction Plan

Extraction order:

1. `ProposalPreviewPanel`
2. `DiscoverySurface`
3. `PurposeSurface`
4. `ChatPanel`
5. `LineagePanel`
6. `MapPanel`
7. `ValidationPanel`
8. `SpecPanel`

Reusable boundaries:

- `panels/DiscoveryPanel.tsx`: accepts items, draft, create/edit/promote/lineage callbacks.
- `panels/PurposePanel.tsx`: accepts items, draft, create/edit/demote/lineage callbacks.
- `panels/ChatPanel.tsx`: accepts messages, draft, draft setter, submit callback.
- `panels/ProposalsPanel.tsx`: accepts proposals, accept/reject callbacks, optional source badge function.
- `panels/LineagePanel.tsx`: accepts label and events.
- `panels/MapPanel.tsx`: accepts map state, filters, and node selection callback, or owns local filters while route/controller owns data.
- `panels/ValidationPanel.tsx`: accepts validation response/checks only.
- `panels/SpecPanel.tsx`: accepts preview/export state and callbacks.

Likely complexity:

- Low: Proposals, Discovery, Purpose, Chat, Lineage.
- Medium: Map, because selection currently navigates back to `/design`.
- Medium-high: Spec/Validation, because Spec route combines builder, validation, sections, export, and export history.

Validation approach:

- First extraction batch should make no visible layout changes.
- Existing tests should pass after each extraction.
- Add static tests for exported panel names and test ids only where they stabilize the contract.
- Avoid large snapshot tests; they will make Dockview integration harder to review.

## 6. Dockview Integration Plan

Shell introduction sequence:

1. Add Dockview dependency in the Dockview batch only.
2. Import Dockview CSS in one place.
3. Wrap `/design` in a workspace container with stable height.
4. Register panel components by stable id.
5. Build default layout through Dockview API on first ready event.
6. Route panel events through the workspace controller, not through global singletons.

Layout definition sequence:

1. Define `WORKSPACE_PANEL_IDS`.
2. Define `DEFAULT_WORKSPACE_LAYOUT_VERSION = 1`.
3. Define default panel grouping in code as the single source of truth.
4. Add tests that assert all required panel ids exist in the default layout.
5. Add narrow-screen default behavior:
   - desktop default shows Proposals and Map visibly;
   - narrow default may tab Map and Proposals together, but Proposals must have a visible tab label and pending count.

Fallback strategy:

- If Dockview integration blocks on React/Vite or CSS issues, preserve the extracted panels and land a static CSS-grid workspace as a temporary fallback.
- If Dockview popout is unstable, ship docked/tabbed behavior first and defer popout to a later dispatch.
- If Dockview persistence format is too opaque, persist only app-level default/reset state initially and defer full layout restore.

## 7. Persistence Plan

Storage key:

```text
design-ui:workspace-layout:v1:{projectId}
```

Stored shape:

```ts
type WorkspaceLayoutStorageV1 = {
  schemaVersion: 1;
  projectId: string;
  updatedAt: string;
  layout: unknown; // Dockview serialized layout
};
```

Rules:

- Persist only layout metadata.
- Do not persist project content, proposals, messages, or validation output.
- Restore only when `schemaVersion === 1` and `projectId` matches.
- On parse failure, unknown schema, missing panel ids, or Dockview restore error, delete or ignore the stored value and load the default layout.
- Reset layout removes the project-specific key and rehydrates the default layout.
- Existing theme storage remains `design-ui:theme`; do not merge theme and layout storage.

Migration/versioning:

- Future incompatible changes increment the key namespace and stored `schemaVersion`.
- v1 does not need migration code beyond fallback-to-default.

## 8. Theme Plan

Lock these token names for Workspace v1 implementation:

- `--workspace-bg`
- `--workspace-chrome-bg`
- `--workspace-panel-bg`
- `--workspace-panel-raised`
- `--workspace-panel-active`
- `--workspace-tab-active`
- `--accent-discovery`
- `--accent-discovery-soft`
- `--accent-purpose`
- `--accent-purpose-soft`
- `--accent-proposal`
- `--accent-proposal-soft`
- `--accent-mcp`
- `--accent-mcp-soft`

Initial color assignments:

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--workspace-bg` | `#f3f6f8` | `#1a1d23` | Workspace body |
| `--workspace-chrome-bg` | `#ffffff` | `#1f242b` | Toolbar and Dockview chrome |
| `--workspace-panel-bg` | `#ffffff` | `#232830` | Normal panel bodies |
| `--workspace-panel-raised` | `#f8fafb` | `#2a2f37` | Cards and raised panel interiors |
| `--workspace-panel-active` | `#e8eef5` | `#303743` | Focused panel chrome |
| `--workspace-tab-active` | `#dfe7ef` | `#3a4150` | Active tab |
| `--accent-discovery` | `#2f80b7` | `#6fa6d2` | Discovery identity |
| `--accent-discovery-soft` | `#e7f2fa` | `#213645` | Discovery soft background |
| `--accent-purpose` | `#2f8a5f` | `#7ec99a` | Purpose identity |
| `--accent-purpose-soft` | `#e8f5ee` | `#1f3b2b` | Purpose soft background |
| `--accent-proposal` | `#9a6400` | `#e0b96d` | Pending proposals |
| `--accent-proposal-soft` | `#fff7e2` | `#3a2f15` | Proposal soft background |
| `--accent-mcp` | `#7a5db5` | `#b79be8` | MCP/Codex source |
| `--accent-mcp-soft` | `#f0ebfa` | `#302842` | MCP/Codex soft background |

Rollout:

- Batch 6 adds tokens to `:root`, system-dark, `[data-theme="light"]`, and `[data-theme="dark"]`.
- Component CSS must reference `var(--token)` only.
- Discovery and Purpose differentiation should use a panel stripe, tab indicator, badge, or metadata treatment; avoid full colored panel backgrounds.
- Dockview built-in theme classes should be overridden through Design UI tokens.

## 9. Testing Strategy

Tests to add:

- Panel registry includes all eight required panels.
- Default workspace layout includes all eight panels exactly once.
- Reset layout removes the project-specific storage key and returns to the default layout.
- Invalid layout storage falls back to default.
- Narrow-screen/default compact behavior keeps Proposals visible or one click away with a pending count.
- MCP-created proposals render a source badge from `proposedChanges.metadata.mcp`.
- Manual/local proposals render a non-MCP source label.
- Theme token tests include new workspace/accent tokens in light, dark, and system layers.

Regression coverage to preserve:

- Discovery and Purpose remain distinct.
- Proposal accept/reject remains the only committed-state mutation path.
- MCP tools create pending proposals only.
- Active context constrains both Discovery and Purpose.
- `/map` and `/spec` remain available.
- Dark/light/system theme behavior remains unchanged.

Operator validation checkpoints:

- After Batch 1: current `/design` looks and behaves the same.
- After Batch 2: `/map` and `/spec` look and behave the same.
- After Batch 4: `/design` opens as a usable workspace with all panels present.
- After Batch 5: layout persists, reset works, corrupted storage recovers.
- After Batch 7: MCP-created proposals are distinguishable and approval-gated.

Commands required for implementation batches:

```sh
npm test
npm run typecheck
npm run build
```

## 10. Proposed Dispatch Sequence

| Task id | Objective | Expected duration/risk | Merge readiness criteria |
| --- | --- | --- | --- |
| DESIGN-WS-IMPL-001 | Extract Chat, Discovery, Purpose, Proposals, and Lineage panels without layout behavior changes | Medium duration, low-medium risk | Existing `/design` behavior unchanged; tests/typecheck/build pass |
| DESIGN-WS-IMPL-002 | Extract Map, Validation, and Spec panels while preserving `/map` and `/spec` | Medium duration, medium risk | Routes unchanged; extracted panels reusable; tests/typecheck/build pass |
| DESIGN-WS-IMPL-003 | Add workspace state controller and panel registry without Dockview | Medium duration, medium risk | Eight panels registered; controller refresh path verified; tests/typecheck/build pass |
| DESIGN-WS-IMPL-004 | Add Dockview and default workspace layout on `/design` | Medium-high duration, high risk | Workspace opens with eight panels; `/map` and `/spec` remain; tests/typecheck/build pass |
| DESIGN-WS-IMPL-005 | Add layout persistence and reset-to-default | Short-medium duration, medium risk | Project-specific persistence works; reset and fallback tested; tests/typecheck/build pass |
| DESIGN-WS-IMPL-006 | Add workspace theme tokens and visual hierarchy | Short-medium duration, medium risk | Tokens locked; no raw CSS colors outside token definitions; light/dark/system checked |
| DESIGN-WS-IMPL-007 | Add MCP proposal source badges, narrow-screen proposal behavior, and limited support-panel popout | Medium duration, medium-high risk | Proposals visible/recoverable on narrow screens; source badges tested; popout compromise documented |

## 11. Risks

1. Dockview integration may alter component lifecycle enough to reset drafts or over-fetch data.
2. Dockview CSS may conflict with the existing token-driven theme system.
3. Proposal visibility can regress on narrow screens if the commit gate is hidden in overflow.
4. Spec extraction can become too broad because validation, preview, sections, export, and history are currently coupled.
5. Popout windows may not restore reliably across browser settings.
6. Layout persistence can trap operators in a bad workspace if fallback/reset is weak.
7. Static text tests may need careful updates as route structure moves from page files to panel files.

## 12. Rollback Strategy

- Batches 1-3 are extraction-only and should preserve the old layout; rollback is reverting component extraction commits.
- Batch 4 should keep the old fixed `DesignRoute` structure available in git history and can be reverted independently if Dockview creates runtime problems.
- If Dockview fails late in Batch 4, land the extracted panels and registry without the Dockview shell, then schedule a replacement library or static fallback batch.
- Batch 5 persistence must fail closed to default layout; deleting the localStorage key must recover the workspace.
- Batch 6 visual changes can be reverted independently if token contrast or theme behavior regresses.
- Batch 7 popout can be disabled without removing docked/tabbed workspace behavior.

## 13. Acceptance Path

Workspace v1 is accepted when:

1. `/design` is the workspace itself.
2. Chat, Discovery, Purpose, Proposals, Map, Lineage, Validation, and Spec are registered and accessible as panels.
3. Chat, Discovery, and Purpose are immediately usable in the default layout.
4. Proposals remain visible on desktop and visibly reachable on narrow screens.
5. Docking, resizing, and tabbing work for registered panels.
6. Popout support exists for support panels or the limitation is explicitly documented.
7. Layout persists locally per project and reset-to-default works.
8. Discovery and Purpose are visually distinct through locked tokens.
9. Dark/light/system theme behavior remains intact.
10. Proposal approval semantics and MCP proposal-only write semantics are unchanged.
11. `/map` and `/spec` remain available.
12. `npm test`, `npm run typecheck`, and `npm run build` pass.

## 14. Recommended First Implementation Batch

Start with DESIGN-WS-IMPL-001: extract Chat, Discovery, Purpose, Proposals, and Lineage panels without changing layout behavior.

Rationale:

- It directly addresses the review note to verify panel extraction before Dockview integration.
- It has no dependency risk.
- It creates reusable component boundaries needed by every later batch.
- It provides a clean before/after verification point because `/design` should remain visually and behaviorally equivalent.
- It minimizes merge conflict risk by avoiding changes to package manifests, build configuration, and Dockview CSS in the first implementation dispatch.
