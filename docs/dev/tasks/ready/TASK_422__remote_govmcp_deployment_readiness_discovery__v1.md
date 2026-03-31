# TASK_422__remote_govmcp_deployment_readiness_discovery__v1

## 1. PURPOSE

Determine from current-main repo truth whether GovMCP is ready, nearly ready, or not ready to be exposed as a remote MCP service usable across Claude surfaces, including iOS, without assuming remote readiness from local MCP capability alone.

## 2. CURRENT_MAIN_SERVER_SURFACE

Current main shows a real GovMCP server surface under [mcp/server.py](../../../../mcp/server.py).

- The file instantiates `FastMCP("governance-broker")` when the MCP runtime is available.
- The same file also contains a bounded stdio test path, `_run_stdio_capabilities_execute()`, that reads one JSON request from `stdin` and writes one JSON response to `stdout`.
- GovMCP exposes a governed tool surface plus receipt-linked inspectability/query methods, including `capabilities.list`, `capabilities.describe`, `capabilities.execute`, `capabilities.receipt`, `capabilities.replay_check`, `capabilities.receipt_tool_events`, and related tool-event query methods.
- Runtime/storage assumptions are present through repo-readable contract files such as [mcp/storage_contract.py](../../../../mcp/storage_contract.py) and [mcp/README.md](../../../../mcp/README.md), which define where receipts, tool-event indexes, bundles, and runtime logs live.

The smallest truthful reading is that GovMCP already exists as a local MCP broker with a real capability surface and a documented local runtime contract.

## 3. TRANSPORT_AND_ENTRYPOINT_FINDINGS

Current main shows **local-only / stdio-oriented transport support**, not a clearly deployable remote transport.

Direct evidence:

- [mcp/README.md](../../../../mcp/README.md) documents only `## Run (stdio)` and gives `python3 mcp/server.py` style commands.
- [tests/run-mcp-smoke.py](../../../../tests/run-mcp-smoke.py) uses `StdioServerParameters` and `stdio_client`, launching `mcp/server.py` as a subprocess.
- [tests/run-mcp-smoke.sh](../../../../tests/run-mcp-smoke.sh) is a local smoke wrapper around that stdio-based client/server path.
- [mcp/server.py](../../../../mcp/server.py) ends with `mcp.run()`, but current main does not document or wrap that call as an HTTP, SSE, or streamable-HTTP service surface.

What current main does **not** show cleanly:

- no explicit remote HTTP listener configuration
- no SSE endpoint docs
- no streamable-HTTP server docs
- no host/port/TLS/ingress startup guidance
- no alternate remote entrypoint file

So the repo supports MCP-style interaction locally, but current main does not evidence a Claude-usable remote transport path as an explicit deployable surface.

## 4. DEPLOYMENT_READINESS_FINDINGS

Code readiness and deployment readiness are not the same on current main.

Code readiness present:

- a runnable GovMCP server module exists
- MCP tool/query surface exists
- runtime root, receipt storage, tool-event storage, and smoke-test conventions are documented
- dependency pinning is documented in [mcp/requirements.txt](../../../../mcp/requirements.txt) and [mcp/README.md](../../../../mcp/README.md)

Deployment readiness absent or ambiguous:

- no deployment manifest, service wrapper, or containerization surface was found
- no remote-hosting instructions were found
- no reverse-proxy or ingress assumptions were documented
- no repo-readable guidance exists for registering a deployed GovMCP endpoint with Claude surfaces
- no repo-readable guidance exists for mobile/iOS-specific remote use beyond the general MCP/local smoke setup

The current-main repo therefore looks stronger on local broker code readiness than on remote deployment readiness.

## 5. AUTH_AND_ACCESS_FINDINGS

Auth/access for remote exposure is **absent** in current-main repo truth.

What is present:

- [mcp/receipt_signing.py](../../../../mcp/receipt_signing.py) provides receipt-signing and verification helpers for evidence integrity.
- Policy enforcement and path/capability controls exist inside the governed tool surface.

What is missing for remote use:

- no bearer-token handling
- no API-key handling
- no OAuth/session flow
- no remote client authentication middleware
- no access-control model for exposing GovMCP to remote Claude clients

Receipt signing is not a substitute for remote client authentication. Current main shows integrity/authenticity for artifacts, not an access-control story for a public or semi-public remote MCP endpoint.

## 6. READINESS_CLASSIFICATION

**NEEDS_SUBSTANTIAL_REMOTE_WORK**

Reason:

- current main evidences local stdio-oriented MCP operation
- current main does not evidence a clearly deployable remote transport surface
- current main does not evidence a remote auth/access model
- current main does not evidence deployment packaging or operator guidance needed to make Claude-on-iOS remote use realistic

This is stronger than "small enablement" because the missing pieces are not just configuration; they include the remote-serving boundary itself plus access assumptions.

## 7. MINIMUM_MISSING_PIECES

Only the minimum missing pieces supported by current-main evidence are listed here:

1. An explicit remote transport surface for GovMCP, with a repo-readable entrypoint and serving assumptions.
2. A deployment-facing startup/config contract for that remote surface, including host/service expectations.
3. A real auth/access-control story for remote clients.
4. A minimal operator/deployment note describing how a remote GovMCP endpoint would actually be exposed to Claude surfaces.

Current main does not need new core GovMCP capability design before that; it needs the remote-serving boundary to become explicit.

## 8. RECOMMENDED_NEXT_STEP

**PLAN_REMOTE_MCP_WORKFRONT**

The next step should be a bounded remote-MCP planning/discovery workfront that defines:

- the intended remote transport shape
- the auth/access stance
- the deployment surface
- the exact smallest tranche needed to move GovMCP from local stdio broker to remote Claude-usable service

Current main does not support jumping directly to remote deployment configuration from repo truth alone.
