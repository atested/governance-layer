# Design UI MCP Integration Design Specification

Task: DESIGN-UI-MCP-SPEC-001
Status: Specification handoff

## 1. Purpose

This document specifies how a local MCP server should integrate with Design UI v1.

The purpose of the MCP integration is to let MCP-enabled AI systems inspect Design UI state and create structured design proposals while preserving the Design UI architecture:

- Design UI remains the authoritative state holder.
- MCP is an adapter layer.
- MCP clients may read committed state.
- MCP clients may create proposals.
- MCP clients may not directly mutate committed Discovery, Purpose, Relationship, Concept, Map, Lineage, Validation, or Spec state.
- Operator approval in Design UI remains the only path to committed-state mutation.

The MCP server is not a replacement UI, workflow engine, autonomous design agent, or secondary source of truth.

## 2. Architectural Overview

Design UI v1 already separates generative input from committed design state:

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

The MCP server must attach to this architecture at the proposal and read boundaries:

```text
MCP client
-> MCP server
-> Design UI local API
-> Design UI proposal store / read APIs
-> operator approval in Design UI
-> committed state and lineage
```

MCP can assist with design work by generating proposals from external reasoning or context, but it must not bypass the operator-facing approval surface.

## 3. MCP Boundary

The MCP server boundary is a local adapter process exposing MCP tools to AI clients.

Inside the boundary:

- translate MCP tool calls into Design UI local API calls;
- normalize Design UI API responses into MCP-friendly structured output;
- attach MCP attribution metadata to proposals;
- enforce that write-capable MCP tools create proposals only.

Outside the boundary:

- Design UI owns SQLite and runtime state;
- Design UI owns proposal acceptance/rejection;
- Design UI owns lineage creation;
- Design UI owns map/context state;
- Design UI owns validation and spec export state.

The MCP server must not expose tools that call internal repository functions directly to mutate committed state.

## 4. Recommended v1 Architecture

Recommended v1 architecture: **MCP server calls the Design UI local HTTP API.**

Do not read SQLite directly in v1.

Reasons:

- The local API is already the Design UI state authority boundary.
- The API already exposes proposal creation, map state, lineage, spec preview, validation, and export behavior.
- Calling the API prevents MCP from depending on private SQLite schema details.
- Calling the API preserves future freedom to change persistence without rewriting the MCP contract.
- API use keeps MCP behavior aligned with the UI’s current semantics.

Rejected option: direct SQLite access.

Direct SQLite reads are tempting because they are fast and local, but they create a second state access path and increase the chance that MCP tools will accidentally depend on private schema or bypass intended API semantics.

Rejected option: hybrid API plus SQLite.

Hybrid access is not justified for v1. It increases complexity and creates ambiguous state authority. If API performance or coverage becomes insufficient, add explicit Design UI API endpoints instead of introducing MCP-side database reads.

Tradeoffs:

| Option | Benefits | Costs | Recommendation |
| --- | --- | --- | --- |
| Local API | Preserves authority, stable boundary, easier testing | Requires Design UI API process or shared server startup | Use for v1 |
| SQLite direct | Fast, fewer HTTP calls | Bypasses API semantics, schema coupling, greater mutation risk | Do not use |
| Hybrid | Flexibility | Ambiguous authority, harder correctness story | Defer |

## 5. Tool Surface

The v1 MCP tool surface should be intentionally small.

Selected read tools:

1. `get_active_project`
2. `get_active_context`
3. `list_discovery_items`
4. `list_purpose_items`
5. `list_relationships`
6. `list_map_nodes`
7. `get_spec_preview`
8. `get_validation_results`

Selected proposal tools:

1. `create_design_proposal`
2. `create_relationship_proposal`
3. `create_promotion_proposal`
4. `create_demotion_proposal`
5. `create_update_proposal`

No v1 MCP tool may accept, reject, or directly commit a proposal.

No v1 MCP tool may create, update, or delete committed Discovery, Purpose, Relationship, Concept, Lineage, Map, Spec, or Validation records directly.

## 6. Tool Schemas

All tools should return structured JSON-compatible objects.

All tools should include a `requestId` in output. The MCP server may generate it if the client does not provide one.

All proposal tools should include `origin` metadata.

```ts
type McpOrigin = {
  clientName: string;
  clientSessionId?: string;
  model?: string;
  userLabel?: string;
  requestId?: string;
};
```

The recommended v1 attribution location is `proposedChanges.metadata.mcp`.

If implementation later adds a first-class proposal metadata column, the MCP spec can migrate attribution there without changing tool semantics.

### 6.1 `get_active_project`

Purpose:

Return the current Design UI project selected by Design UI’s v1 project behavior.

Input schema:

```ts
type GetActiveProjectInput = {
  requestId?: string;
};
```

Output schema:

```ts
type GetActiveProjectOutput = {
  requestId: string;
  project: {
    id: string;
    title: string;
    activeContextId: string | null;
    createdAt: string;
    updatedAt: string;
  } | null;
};
```

Allowed side effects:

- none.

Forbidden side effects:

- creating projects;
- changing active context;
- mutating Design UI state.

Failure modes:

- Design UI API unavailable;
- no project exists;
- unexpected API response shape.

### 6.2 `get_active_context`

Purpose:

Return the active map/context selection for a project.

Input schema:

```ts
type GetActiveContextInput = {
  projectId: string;
  requestId?: string;
};
```

Output schema:

```ts
type GetActiveContextOutput = {
  requestId: string;
  activeContext: {
    id: string;
    label: string;
    discoveryItemIds: string[];
    purposeItemIds: string[];
    conceptIds: string[];
    relationshipIds: string[];
  } | null;
};
```

Allowed side effects:

- none.

Forbidden side effects:

- selecting a map node;
- creating or replacing active context.

Failure modes:

- missing or invalid `projectId`;
- Design UI API unavailable.

### 6.3 `list_discovery_items`

Purpose:

Read committed Discovery items for a project, optionally constrained to active context.

Input schema:

```ts
type ListDiscoveryItemsInput = {
  projectId: string;
  contextOnly?: boolean;
  state?: string;
  discoveryType?: string;
  requestId?: string;
};
```

Output schema:

```ts
type ListDiscoveryItemsOutput = {
  requestId: string;
  items: Array<{
    id: string;
    title: string;
    body: string;
    discoveryType: string;
    state: string;
    createdAt: string;
    updatedAt: string;
  }>;
};
```

Allowed side effects:

- none.

Forbidden side effects:

- creating, editing, promoting, demoting, or deleting Discovery items.

Failure modes:

- invalid filter values;
- Design UI API unavailable.

### 6.4 `list_purpose_items`

Purpose:

Read committed Purpose items for a project, optionally constrained to active context.

Input schema:

```ts
type ListPurposeItemsInput = {
  projectId: string;
  contextOnly?: boolean;
  state?: string;
  purposeType?: string;
  requestId?: string;
};
```

Output schema:

```ts
type ListPurposeItemsOutput = {
  requestId: string;
  items: Array<{
    id: string;
    title: string;
    body: string;
    purposeType: string;
    state: string;
    createdAt: string;
    updatedAt: string;
  }>;
};
```

Allowed side effects:

- none.

Forbidden side effects:

- creating, editing, promoting, demoting, or deleting Purpose items.

Failure modes:

- invalid filter values;
- Design UI API unavailable.

### 6.5 `list_relationships`

Purpose:

Read committed relationships for a project.

Input schema:

```ts
type ListRelationshipsInput = {
  projectId: string;
  itemId?: string;
  relationshipType?: string;
  requestId?: string;
};
```

Output schema:

```ts
type ListRelationshipsOutput = {
  requestId: string;
  relationships: Array<{
    id: string;
    fromId: string;
    toId: string;
    type: string;
    description: string;
    createdAt: string;
  }>;
};
```

Allowed side effects:

- none.

Forbidden side effects:

- creating or deleting relationships.

Failure modes:

- invalid project;
- API unavailable.

### 6.6 `list_map_nodes`

Purpose:

Read the Design Map node/edge projection.

Input schema:

```ts
type ListMapNodesInput = {
  projectId: string;
  nodeType?: "concept" | "discovery_cluster" | "purpose_region" | "tension" | "open_area" | "disconnected_idea";
  maturity?: string;
  connected?: boolean;
  requestId?: string;
};
```

Output schema:

```ts
type ListMapNodesOutput = {
  requestId: string;
  nodes: Array<{
    id: string;
    label: string;
    nodeType: string;
    maturity: string;
    connected: boolean;
    sourceKind: "concept" | "discovery" | "purpose";
    sourceId: string;
  }>;
  edges: Array<{
    id: string;
    fromId: string;
    toId: string;
    type: string;
    description: string;
  }>;
};
```

Allowed side effects:

- none.

Forbidden side effects:

- selecting active context;
- creating map nodes;
- mutating relationships.

Failure modes:

- invalid filters;
- map API unavailable.

### 6.7 `get_spec_preview`

Purpose:

Read the current Design Specification preview generated from committed Purpose state.

Input schema:

```ts
type GetSpecPreviewInput = {
  projectId: string;
  format?: "markdown" | "json" | "both";
  requestId?: string;
};
```

Output schema:

```ts
type GetSpecPreviewOutput = {
  requestId: string;
  markdown?: string;
  json?: string;
  sourcePurposeItemIds: string[];
  sourceLineageEventIds: string[];
};
```

Allowed side effects:

- none.

Forbidden side effects:

- persisting exports;
- modifying spec sections;
- mutating validation state.

Failure modes:

- invalid format;
- Design UI API unavailable.

### 6.8 `get_validation_results`

Purpose:

Read current advisory validation results.

Input schema:

```ts
type GetValidationResultsInput = {
  projectId: string;
  requestId?: string;
};
```

Output schema:

```ts
type ValidationCheck = {
  status: "pass" | "warning" | "fail";
  message: string;
  relatedItemIds: string[];
};

type GetValidationResultsOutput = {
  requestId: string;
  passed: boolean;
  checks: {
    purposeClarity: ValidationCheck;
    expectationClarity: ValidationCheck;
    operationalIntentPreserved: ValidationCheck;
    confusionRiskAddressed: ValidationCheck;
    examplesAdequate: ValidationCheck;
    boundariesPresent: ValidationCheck;
    residualJudgmentsPresent: ValidationCheck;
    downstreamRediscoveryRisk: ValidationCheck;
  };
};
```

Allowed side effects:

- none.

Forbidden side effects:

- changing validation outcomes;
- blocking export;
- committing remediation changes.

Failure modes:

- invalid project;
- Design UI API unavailable.

### 6.9 `create_design_proposal`

Purpose:

Create a pending proposal for a new Discovery or Purpose item.

Input schema:

```ts
type CreateDesignProposalInput = {
  projectId: string;
  targetKind: "discovery" | "purpose";
  title: string;
  body?: string;
  discoveryType?: string;
  purposeType?: string;
  rationale: string;
  sourceMessageIds?: string[];
  origin: McpOrigin;
  requestId?: string;
};
```

Output schema:

```ts
type CreateDesignProposalOutput = {
  requestId: string;
  proposal: {
    id: string;
    projectId: string;
    proposalType: "create_discovery" | "create_purpose";
    status: "pending";
    rationale: string;
    proposedChanges: unknown;
    preview: unknown;
    createdAt: string;
  };
};
```

Allowed side effects:

- create one pending proposal.

Forbidden side effects:

- creating committed Discovery or Purpose items;
- creating lineage;
- accepting the proposal.

Failure modes:

- missing required title/rationale/origin;
- invalid `targetKind`;
- Design UI API unavailable.

### 6.10 `create_relationship_proposal`

Purpose:

Create a pending proposal to connect two existing design objects.

Input schema:

```ts
type CreateRelationshipProposalInput = {
  projectId: string;
  fromId: string;
  toId: string;
  relationshipType?: "supports" | "contrasts" | "depends_on" | "refines" | "challenges" | "supersedes" | "related_to";
  description?: string;
  rationale: string;
  sourceMessageIds?: string[];
  origin: McpOrigin;
  requestId?: string;
};
```

Output schema:

```ts
type CreateRelationshipProposalOutput = {
  requestId: string;
  proposal: {
    id: string;
    proposalType: "connect_items";
    status: "pending";
    preview: unknown;
  };
};
```

Allowed side effects:

- create one pending relationship proposal.

Forbidden side effects:

- creating committed relationships;
- mutating map edges;
- creating lineage.

Failure modes:

- missing endpoints;
- endpoints not readable by project scope;
- Design UI API unavailable.

### 6.11 `create_promotion_proposal`

Purpose:

Create a pending proposal to promote a Discovery item into Purpose.

Input schema:

```ts
type CreatePromotionProposalInput = {
  projectId: string;
  sourceDiscoveryItemId: string;
  title?: string;
  body?: string;
  purposeType?: string;
  rationale: string;
  sourceMessageIds?: string[];
  origin: McpOrigin;
  requestId?: string;
};
```

Output schema:

```ts
type CreatePromotionProposalOutput = {
  requestId: string;
  proposal: {
    id: string;
    proposalType: "promote_to_purpose";
    status: "pending";
    preview: unknown;
  };
};
```

Allowed side effects:

- create one pending promotion proposal.

Forbidden side effects:

- marking Discovery as superseded;
- creating Purpose;
- creating lineage.

Failure modes:

- source Discovery item missing;
- invalid Purpose type;
- Design UI API unavailable.

### 6.12 `create_demotion_proposal`

Purpose:

Create a pending proposal to demote a Purpose item back to Discovery.

Input schema:

```ts
type CreateDemotionProposalInput = {
  projectId: string;
  sourcePurposeItemId: string;
  title?: string;
  body?: string;
  discoveryType?: string;
  rationale: string;
  sourceMessageIds?: string[];
  origin: McpOrigin;
  requestId?: string;
};
```

Output schema:

```ts
type CreateDemotionProposalOutput = {
  requestId: string;
  proposal: {
    id: string;
    proposalType: "demote_to_discovery";
    status: "pending";
    preview: unknown;
  };
};
```

Allowed side effects:

- create one pending demotion proposal.

Forbidden side effects:

- marking Purpose as superseded;
- creating Discovery;
- creating lineage.

Failure modes:

- source Purpose item missing;
- invalid Discovery type;
- Design UI API unavailable.

### 6.13 `create_update_proposal`

Purpose:

Create a pending proposal to update a committed design object.

Input schema:

```ts
type CreateUpdateProposalInput = {
  projectId: string;
  targetTable: "discovery_items" | "purpose_items" | "concepts" | "relationships";
  targetId: string;
  patch: Record<string, unknown>;
  rationale: string;
  sourceMessageIds?: string[];
  origin: McpOrigin;
  requestId?: string;
};
```

Output schema:

```ts
type CreateUpdateProposalOutput = {
  requestId: string;
  proposal: {
    id: string;
    proposalType: "update_item";
    status: "pending";
    preview: unknown;
  };
};
```

Allowed side effects:

- create one pending update proposal.

Forbidden side effects:

- applying the patch directly;
- creating lineage;
- changing validation/spec/map state directly.

Failure modes:

- invalid target table;
- target not found;
- patch includes forbidden fields such as `projectId`, `id`, `createdAt`, or lineage fields;
- Design UI API unavailable.

## 7. Data Flow

Read flow:

```text
AI client
-> MCP read tool
-> MCP server
-> Design UI local API
-> committed Design UI state projection
-> MCP response
-> AI client
```

Proposal flow:

```text
AI client
-> MCP proposal tool
-> MCP server
-> Design UI local API /api/proposals
-> pending proposal
-> Design UI proposal preview
-> operator approval or rejection
```

Commit flow after operator approval:

```text
operator approval in Design UI
-> Design UI proposal committer
-> committed state mutation
-> lineage creation
-> proposal status accepted
-> map/spec/validation projections update from committed state
```

MCP is not in the commit flow.

## 8. Proposal Flow

Required flow:

```text
AI client
-> MCP server
-> Design UI proposal
-> operator approval in Design UI
-> committed state
-> lineage
```

MCP can see:

- current project metadata;
- active context;
- committed Discovery/Purpose/Relationship projections;
- map nodes and edges;
- spec preview;
- validation results;
- proposal creation responses for proposals it submits.

MCP can create:

- pending proposals only.

Approval occurs:

- in the Design UI operator surface;
- never in MCP tools;
- never automatically in the MCP server.

Impossible through MCP:

- accept proposal;
- reject proposal;
- directly create committed Discovery/Purpose/Relationship/Concept records;
- directly create lineage;
- directly replace active context;
- directly persist spec exports;
- directly change validation results.

## 9. Attribution Model

MCP-created proposals must be identifiable at proposal creation time and after approval.

Recommended v1 metadata embedded in `proposedChanges`:

```ts
type McpProposalMetadata = {
  mcp: {
    createdVia: "mcp";
    clientName: string;
    clientSessionId?: string;
    model?: string;
    userLabel?: string;
    requestId?: string;
    createdAt: string;
  };
};
```

Example:

```json
{
  "title": "Both surfaces remain visible",
  "purposeType": "constraint",
  "metadata": {
    "mcp": {
      "createdVia": "mcp",
      "clientName": "codex",
      "model": "gpt-5",
      "requestId": "req_123",
      "createdAt": "2026-05-30T00:00:00.000Z"
    }
  }
}
```

Lineage after approval:

- Design UI already stores `proposalId` on lineage events created from accepted proposals.
- The proposal stores MCP attribution in `proposedChanges.metadata.mcp`.
- A lineage viewer can resolve `proposalId` to the proposal and display MCP provenance.

Recommended future improvement:

- add a first-class `metadata` column to `proposals`;
- include MCP origin in proposal preview;
- include MCP origin in lineage panel without needing to inspect `proposedChanges`.

## 10. Trust Model

V1 assumption:

- local-first trusted operation;
- MCP server runs on the same machine or trusted local network as Design UI;
- MCP client is authorized by the operator to inspect local Design UI state.

Trusted:

- local MCP server process;
- local Design UI API endpoint;
- operator-controlled MCP client configuration.

Protected despite local trust:

- committed-state mutation;
- proposal acceptance/rejection;
- lineage creation;
- spec export persistence;
- map active context mutation.

Why committed-state mutation remains protected:

- preserving operator approval is the core Design UI safety and meaning boundary;
- design state represents accepted meaning, not AI suggestion;
- lineage must reflect operator-approved changes, not autonomous MCP writes.

Future extension points:

- local auth token for Design UI API;
- MCP client allowlist;
- per-tool permission policy;
- signed MCP attribution metadata;
- audit log for MCP tool calls;
- workspace-level trust profiles.

## 11. Acceptance Tests

Read operations:

1. Start Design UI local API.
2. Create project and committed items through existing app/API behavior.
3. Call each MCP read tool.
4. Verify returned state matches Design UI API state.
5. Verify no Design UI tables are mutated by read tools.

Proposal creation:

1. Call each MCP proposal tool.
2. Verify a pending proposal exists.
3. Verify proposal preview is available.
4. Verify committed Discovery/Purpose/Relationship/Concept tables are unchanged.

Approval preservation:

1. Create a proposal through MCP.
2. Verify MCP cannot accept it.
3. Accept it through Design UI.
4. Verify committed state changes only after Design UI approval.

Lineage preservation:

1. Accept an MCP-created proposal in Design UI.
2. Verify lineage event exists.
3. Verify lineage event includes `proposalId`.
4. Verify MCP attribution can be resolved through the proposal.

Map/context integration:

1. Create committed items and relationships.
2. Read map through MCP.
3. Verify nodes, edges, maturity, and disconnected ideas are present.
4. Verify MCP cannot create or replace active context.

Validation integration:

1. Read validation results through MCP.
2. Verify pass/warning/fail shape.
3. Verify missing boundaries/examples produce warning or fail.
4. Verify MCP cannot change validation outcomes.

No direct committed-state mutation:

1. Attempt to call all MCP tools with mutation-like input.
2. Verify only proposal records are created.
3. Verify committed tables are unchanged until Design UI approval.

## 12. Open Questions

1. Should MCP tools support multiple projects explicitly, or should v1 expose only the currently active/first Design UI project?
2. Should proposal attribution remain embedded in `proposedChanges.metadata`, or should proposal metadata become a first-class schema column before MCP implementation?
3. Should MCP expose pending proposal listing, or is proposal creation plus Design UI review sufficient for v1?
4. Should MCP be allowed to request Design UI active context changes through proposals, or should active context remain UI-only?
5. Should spec export persistence remain UI/API-only, or should MCP eventually be allowed to request export proposals?

## 13. Recommended v1 Scope

Implement a local MCP server that:

- calls Design UI local API only;
- exposes the selected read tools;
- exposes the selected proposal creation tools;
- embeds MCP attribution metadata in created proposals;
- never accepts or rejects proposals;
- never writes committed design state directly;
- includes tests proving proposal-only side effects;
- assumes trusted local operation.

Do not add:

- direct SQLite access;
- real AI integration;
- remote auth;
- automatic proposal approval;
- direct spec export persistence;
- direct active-context mutation.

## 14. Deferred v2 Scope

Potential v2 capabilities:

- first-class proposal metadata storage;
- MCP pending-proposal listing;
- MCP proposal provenance display in UI;
- optional authentication and client authorization;
- remote MCP operation through explicit trust configuration;
- richer contextual read APIs for lineage and map neighborhoods;
- tool-call audit trail;
- per-project MCP permissions;
- explicit context-change proposal type.

## 15. Implementation Handoff Notes

Implementation should start by wrapping the existing local API:

- `GET /api/projects`
- `GET /api/items?kind=discovery`
- `GET /api/items?kind=purpose`
- `GET /api/map`
- `GET /api/spec`
- `POST /api/proposals`

The implementation should not import Design UI repository modules or open SQLite directly.

Proposal tool mapping:

| MCP tool | Design UI proposalType |
| --- | --- |
| `create_design_proposal` with `targetKind=discovery` | `create_discovery` |
| `create_design_proposal` with `targetKind=purpose` | `create_purpose` |
| `create_relationship_proposal` | `connect_items` |
| `create_promotion_proposal` | `promote_to_purpose` |
| `create_demotion_proposal` | `demote_to_discovery` |
| `create_update_proposal` | `update_item` |

Implementation must include a negative test proving MCP cannot directly mutate committed state.

The first implementation dispatch should be scoped to a local server, API client wrapper, tool registration, proposal creation, attribution metadata, and tests. It should not alter Design UI approval or commit semantics.
