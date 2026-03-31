1. PURPOSE

Assess and, if possible within a bounded tranche, implement the minimum OAuth-compatible remote auth path needed for Claude remote connectors to authenticate to GovMCP without changing the already-landed remote serving and deployment boundary.

2. CURRENT_MAIN_AUTH_LIMITATION

Current main exposes only a custom shared bearer-token auth path for remote GovMCP:

- remote service admission currently depends on:
  - `GOVMCP_REMOTE_AUTH_TOKEN`
  - or `GOVMCP_REMOTE_AUTH_TOKEN_FILE`
- the deployment contract still tells clients to send:
  - `Authorization: Bearer <configured token>`

Why this is insufficient for Claude connector use:

- Claude remote connectors do not expose a generic UI for manually supplying an arbitrary pre-shared bearer token to the MCP endpoint
- the pinned MCP SDK’s Claude-compatible auth surface is OAuth-oriented:
  - `AuthSettings`
  - `TokenVerifier`
  - `OAuthAuthorizationServerProvider`
  - authorization-server metadata
  - protected-resource metadata

So the remaining compatibility gap is not “accept bearer tokens” in general; it is “provide a real OAuth authorization path Claude can use.”

3. OAUTH_COMPATIBILITY_SCOPE

What would need to be added for bounded OAuth compatibility:

- an OAuth resource/auth path that Claude can discover and use
- server-side token validation for OAuth-issued access tokens
- fail-closed startup/serving when OAuth mode is required but not configured
- truthful runtime/config docs for that mode

What this tranche did not add:

- no authorization server/provider implementation
- no client registration policy
- no redirect/approval UX
- no user/account system
- no external identity-provider integration

4. IMPLEMENTATION

No code implementation was performed in this tranche.

Why:

- repo inspection confirmed the pinned MCP SDK can support OAuth only if we provide one of:
  - a `TokenVerifier` wired to an external issuer/token system
  - or an `OAuthAuthorizationServerProvider` implementation that defines client registration, authorization-code issuance, token exchange, refresh, access-token loading, and revocation behavior
- current main contains neither:
  - no provider implementation
  - no issuer integration
  - no client registration policy
  - no authorization/approval surface
- adding any of those now would require choosing identity/provider semantics that are not already present in repo truth

This is the exact blocking boundary for the tranche.

5. OAUTH_RUNTIME_CONFIG_CONTRACT

No new OAuth runtime/config contract was introduced because the repo does not yet have a truthful OAuth provider/issuer choice to bind configuration to.

The missing decision is at least one of:

- external issuer / introspection / JWKS style verification contract
- in-repo OAuth authorization-server/provider contract

Without that choice, any new OAuth env vars would be speculative.

6. VERIFICATION

Verification performed in this tranche:

- confirmed current remote service/auth shape remains bearer-token based in:
  - [mcp/remote_server.py](/Volumes/SSD/archive/gov/governance-layer/mcp/remote_server.py)
  - [mcp/remote_deploy.py](/Volumes/SSD/archive/gov/governance-layer/mcp/remote_deploy.py)
  - [mcp/README.md](/Volumes/SSD/archive/gov/governance-layer/mcp/README.md)
- confirmed pinned MCP SDK has OAuth hook points but requires missing provider/issuer semantics:
  - `mcp.server.auth.settings.AuthSettings`
  - `mcp.server.auth.provider.TokenVerifier`
  - `mcp.server.auth.provider.OAuthAuthorizationServerProvider`
  - `mcp.server.auth.routes.create_auth_routes`
- confirmed no secret material was written into repo paths

Connector-compatible OAuth flow check:

- not implementable truthfully from current-main repo evidence without first choosing an issuer/provider model

7. OUT_OF_SCOPE

- inventing an authorization server/provider model
- inventing client registration semantics
- inventing redirect/approval UX
- multi-user or account-system work
- broader deployment/provider redesign

8. STOP_BOUNDARIES

- Stopped because honest OAuth compatibility requires a broader authorization-server / issuer decision than this bounded tranche can make from current-main truth.
- Did not implement a fake OAuth facade or relabel the bearer-token path as OAuth.
