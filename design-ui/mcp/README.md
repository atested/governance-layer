# Design UI MCP Server

The Design UI MCP server is a local stdio adapter for MCP-capable clients. It lets an AI client read Design UI state and create pending proposals through the Design UI local API.

It does not approve proposals and does not mutate committed Design UI state directly.

## Prerequisites

Start Design UI first:

```sh
npm run dev
```

The MCP server expects the Design UI API at:

```text
http://127.0.0.1:4174/api
```

Override this with:

```sh
DESIGN_UI_API_URL=http://127.0.0.1:4174/api
```

## Run

From `design-ui/`:

```sh
npm run mcp
```

Equivalent:

```sh
npm run mcp:stdio
```

The server uses stdio transport for local MCP clients.

## Codex Configuration Example

Add a local MCP server entry pointing at this package. Adjust paths for your checkout.

```toml
[mcp_servers.design-ui]
command = "npm"
args = ["--prefix", "/Volumes/SSD/ai-systems/codex-workspaces/governance-layer/design-ui", "run", "mcp"]
env = { DESIGN_UI_API_URL = "http://127.0.0.1:4174/api" }
```

Design UI must be running before MCP tools can read API state.

## Tools

Read tools:

- `get_active_project`
- `get_active_context`
- `list_discovery_items`
- `list_purpose_items`
- `list_relationships`
- `list_map_nodes`
- `get_spec_preview`
- `get_validation_results`

Proposal tools:

- `create_design_proposal`
- `create_relationship_proposal`
- `create_promotion_proposal`
- `create_demotion_proposal`
- `create_update_proposal`

Proposal tools create pending proposals only. Operator approval still happens in the Design UI.

## Attribution

Proposal tools embed MCP attribution in:

```text
proposedChanges.metadata.mcp
```

The metadata includes:

- `createdBy: "mcp"`
- client/source name
- MCP tool name
- timestamp
- rationale

If Design UI later adds first-class proposal metadata, this adapter can migrate attribution there without changing tool behavior.
