# Design UI v1 Verification Report

Dispatch: DESIGN-UI-009
Branch: design-ui-009-v1-verification
Date: 2026-05-30

## Result

Design UI v1 is release-ready for the defined local v1 scope.

The verified loop works end to end:

```text
chat/manual input
-> proposal
-> approval
-> committed Discovery/Purpose state
-> lineage
-> Design Map
-> active context
-> Design Specification
-> validation
-> export
```

## Verification Coverage

Foundation:
- React/Vite app builds.
- Local Node API starts.
- SQLite initializes.
- Required schema exists.
- Project-scoped storage is covered by tests.

Proposal workflow:
- Stub chat and manual actions create proposals.
- Proposal previews are generated.
- Pending proposals do not mutate committed state.
- Accepted proposals mutate committed state and create lineage.
- Rejected proposals leave committed state unchanged.
- Proposal status transitions are covered by tests and end-to-end smoke.

Discovery/Purpose working surface:
- Discovery and Purpose surfaces remain present.
- Focus switching changes layout ratio rather than hiding a surface.
- Manual Discovery and Purpose creation work.
- Promotion and demotion flow through proposals.
- Proposal previews render in the working screen.

Lineage:
- Committed manual and proposal mutations create lineage.
- Lineage API returns chronological playback data.
- Proposal and chat references are preserved where available.
- Item-level lineage panel is present in `/design`.

Design Map:
- `/map` renders a node-link style map, not a tree.
- Nodes, relationships, disconnected ideas, maturity, and filters are represented.
- Selecting a node creates active context.
- `/design` respects active context while keeping both surfaces visible.

Design Specification Builder:
- `/spec` renders builder, preview, validation, and export controls.
- Markdown and JSON export work.
- Exports are persisted in `spec_exports`.
- All 16 required sections are present.
- Discovery content appears only as reference/context, not as Purpose instruction.
- Lineage and relationship references are included.

Validation:
- Validation returns pass/warning/fail checks.
- Missing purpose, boundaries, examples, and confusion-risk material are surfaced.
- Validation is advisory.
- Export remains possible despite warnings.

## Architecture Assessment

The v1 architecture matches the intended separation:

- Chat remains generative input.
- Proposals are separate from committed design state.
- Accepted proposals are the boundary where committed state changes.
- Lineage records preserve the history of committed mutations.
- The map is an orientation surface over committed concepts/items/relationships.
- The spec builder compiles committed Purpose state and references Discovery only as supporting context.

No critical architectural violations were found.

## Corrective Fix Applied

Active-context filtering in `/design` was tightened.

Before this verification pass, selecting a map node with only Discovery context could still show all Purpose items because each surface was filtered only when the active context had IDs for that surface.

The fix makes an active context constrain both surfaces:

- if selected context has Discovery IDs, Discovery shows those IDs;
- if selected context has no Purpose IDs, Purpose shows empty;
- both surfaces remain visible.

A regression test was added to preserve this behavior.

## Commands Run

```text
npm_config_cache=/private/tmp/design-ui-npm-cache npm install
npm test
npm run typecheck
npm run build
node --no-warnings --input-type=module <end-to-end verification script>
```

The end-to-end script started the API and Vite programmatically, used an isolated temporary SQLite database, verified the complete workflow, then closed both servers.

## Known Limitations

- No real AI calls are implemented; proposal generation is deterministic stub logic.
- The map is a simple node-link layout, not a graph analytics or force-directed graph engine.
- Lineage playback is a chronological list, not a visual timeline.
- Validation is heuristic and deterministic.
- The UI is intentionally minimal and not yet polished.
- There is no multi-project selector beyond using the first existing project.
- There is no multi-user collaboration.
- There is no Tailscale/public deployment configuration in v1.

## Recommended v2 Priorities

1. Replace stub proposal generation with model-backed extraction behind the existing proposal contract.
2. Add richer proposal diff previews for update, split, merge, and relationship changes.
3. Add a project selector and project lifecycle management.
4. Improve the map with spatial layout, search, and stronger visual grouping.
5. Add richer lineage playback with event filtering and replay controls.
6. Add spec export download buttons and copy-to-clipboard affordances.
7. Expand validation to explain remediation options per failed check.
8. Add browser-level UI tests for focus switching, active-context loading, and export flows.

## Release Readiness

Ready for release within the v1 local-app scope.
