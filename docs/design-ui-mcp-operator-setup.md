# Design UI MCP Operator Setup

This guide configures Codex to use the local Design UI MCP server.

The MCP server lets Codex read Design UI state and create pending proposals. It cannot approve proposals, reject proposals, or directly mutate committed Discovery, Purpose, Relationship, Concept, Map, Lineage, Spec, or active context state. Operator approval still happens inside Design UI.

## 1. Start Design UI

From the repo root:

```sh
./scripts/run-design-ui.sh
```

Or from any directory, call the launcher by absolute path:

```sh
/absolute/path/to/governance-layer/scripts/run-design-ui.sh
```

Default local URLs:

| Surface | URL |
| --- | --- |
| Design | `http://127.0.0.1:5173/design` |
| Map | `http://127.0.0.1:5173/map` |
| Spec | `http://127.0.0.1:5173/spec` |
| API health | `http://127.0.0.1:4174/api/health` |

Leave Design UI running while Codex uses the MCP tools.

## 2. Print The Codex MCP Config Snippet

From the repo root:

```sh
./scripts/print-design-ui-mcp-config.sh
```

Or from any directory:

```sh
/absolute/path/to/governance-layer/scripts/print-design-ui-mcp-config.sh
```

The script resolves the repo path from its own location and prints a ready-to-paste TOML snippet with:

- the absolute `design-ui/` path;
- the `npm --prefix ... run mcp` launch command;
- `DESIGN_UI_API_URL`, defaulting to `http://127.0.0.1:4174/api`;
- a reminder that Design UI must be running first.

To use a different API URL, set it before printing:

```sh
DESIGN_UI_API_URL=http://127.0.0.1:4174/api ./scripts/print-design-ui-mcp-config.sh
```

## 3. Paste Into Codex Config

Codex reads local MCP server definitions from:

```text
~/.codex/config.toml
```

Open or create that file, then paste the snippet printed by:

```sh
./scripts/print-design-ui-mcp-config.sh
```

The snippet will look like this, with your actual absolute path:

```toml
[mcp_servers.design-ui]
command = "npm"
args = ["--prefix", "/absolute/path/to/governance-layer/design-ui", "run", "mcp"]
env = { DESIGN_UI_API_URL = "http://127.0.0.1:4174/api" }
```

Do not add an accept/reject tool. The MCP server is intentionally proposal-only for writes.

Restart Codex after editing `~/.codex/config.toml` so it reloads MCP server configuration.

## 4. Optional Prereq Check

Run:

```sh
./scripts/check-design-ui-mcp-prereqs.sh
```

This checks:

- Node is available;
- npm is available;
- `design-ui/package.json` exists;
- `design-ui/mcp/server.ts` exists;
- dependencies are present or installable;
- the MCP server imports successfully;
- the Design UI API is reachable at `DESIGN_UI_API_URL`.

If the API reachability check warns, start Design UI with `./scripts/run-design-ui.sh` and run the prereq check again.

## 5. Verify Codex Sees The Tools

After restarting Codex, ask it to use the Design UI MCP server or list available Design UI MCP tools. The expected tool names are:

- `get_active_project`
- `get_active_context`
- `list_discovery_items`
- `list_purpose_items`
- `list_relationships`
- `list_map_nodes`
- `get_spec_preview`
- `get_validation_results`
- `create_design_proposal`
- `create_relationship_proposal`
- `create_promotion_proposal`
- `create_demotion_proposal`
- `create_update_proposal`

If the tools do not appear, check:

1. The snippet is pasted into `~/.codex/config.toml`.
2. Codex was restarted after editing the file.
3. The `args` path points at the real `design-ui/` directory.
4. `npm --prefix /absolute/path/to/governance-layer/design-ui run mcp` starts without a module error.

## 6. Troubleshoot API Not Running

If Codex reports that the Design UI API is unavailable:

1. Start Design UI:

   ```sh
   ./scripts/run-design-ui.sh
   ```

2. Confirm API health in another terminal:

   ```sh
   curl http://127.0.0.1:4174/api/health
   ```

3. If you changed the API port, print a new config snippet with the matching API URL:

   ```sh
   DESIGN_UI_API_URL=http://127.0.0.1:NEW_PORT/api ./scripts/print-design-ui-mcp-config.sh
   ```

4. Paste the updated snippet into `~/.codex/config.toml` and restart Codex.

## 7. Confirm Proposals Appear In Design UI

Use a proposal tool such as `create_design_proposal` from Codex with the active `projectId`.

Then open:

```text
http://127.0.0.1:5173/design
```

The proposal should appear as a pending proposal preview. Accepting or rejecting that proposal must be done in Design UI by the operator.

## Non-Goals And Boundaries

- MCP does not replace Design UI.
- MCP does not approve or reject proposals.
- MCP does not directly create committed Discovery or Purpose items.
- MCP does not directly create committed relationships.
- MCP does not mutate map, active context, lineage, validation, spec, or export state.
- MCP does not add real AI extraction inside Design UI.

The intended flow is:

```text
Codex or another MCP client
-> Design UI MCP server
-> Design UI local API
-> pending proposal
-> operator approval in Design UI
-> committed state and lineage
```
