1. PURPOSE

Bring remote GovMCP up in live OIDC mode using the real Auth0 issuer and audience values, verify the public connector-facing OAuth surface, and determine whether anything besides the actual Claude-side login attempt still blocks a real connector trial.

2. LIVE_OIDC_CONFIG

Live values applied in this tranche:

- `GOVMCP_REMOTE_AUTH_MODE=oidc`
- `GOVMCP_OIDC_ISSUER_URL=https://dev-cizyho1vgel1c1g1.us.auth0.com`
- `GOVMCP_OIDC_AUDIENCE=https://govmcp.local/api`
- `GOVMCP_PUBLIC_BASE_URL=https://mac-mini.tail341fb0.ts.net`
- `GOVMCP_HOST=127.0.0.1`
- `GOVMCP_PORT=6100`
- `GOVMCP_STREAMABLE_HTTP_PATH=/mcp`
- `GOVMCP_LOG_LEVEL=ERROR`
- `GOV_RUNTIME_DIR=/Volumes/SSD/archive/gov/governance-layer/gov_runtime`

Live OIDC deployment contract printed successfully and resolved to:

- public MCP URL:
  - `https://mac-mini.tail341fb0.ts.net/mcp`
- protected-resource metadata URL:
  - `https://mac-mini.tail341fb0.ts.net/.well-known/oauth-protected-resource/mcp`

3. SERVICE_RESULT

The OIDC-mode GovMCP service started successfully on:

- local bind:
  - `127.0.0.1:6100`

Public connector-facing verification succeeded:

- protected-resource metadata over Funnel:
  - `GET https://mac-mini.tail341fb0.ts.net/.well-known/oauth-protected-resource/mcp`
  - result: `200 OK`
  - returned:
    - `resource=https://mac-mini.tail341fb0.ts.net/mcp`
    - `authorization_servers=["https://dev-cizyho1vgel1c1g1.us.auth0.com/"]`
- unauthenticated connector path:
  - `GET https://mac-mini.tail341fb0.ts.net/mcp`
  - result: `401`
  - `WWW-Authenticate` header included:
    - `error="invalid_token"`
    - `error_description="Authentication required"`
    - `resource_metadata="https://mac-mini.tail341fb0.ts.net/.well-known/oauth-protected-resource/mcp"`

Result:

- the public GovMCP endpoint now exposes a real OAuth/OIDC resource-server surface rather than raw bearer-token-only semantics

4. CONNECTOR_READY_VALUES

Exact connector-facing values now ready:

- remote MCP URL:
  - `https://mac-mini.tail341fb0.ts.net/mcp`
- auth mode:
  - OAuth / OIDC
- advertised authorization server:
  - `https://dev-cizyho1vgel1c1g1.us.auth0.com/`
- GovMCP resource / audience expectation:
  - `https://govmcp.local/api`

Practical connector note:

- the issuer is published by GovMCP through protected-resource metadata
- the public MCP URL is the value Greg should use as the Claude connector target

5. TRUE_REMAINING_BLOCKER

NONE

From the repo side and the public GovMCP/OIDC surface, there is no remaining local or server-side blocker visible in this tranche.

6. NEXT_OPERATOR_STEP

Minimum next action outside the repo:

- In Claude, add the remote MCP server using:
  - `https://mac-mini.tail341fb0.ts.net/mcp`
- Choose OAuth/OIDC auth when prompted and attempt the live Auth0 login flow.

If the Claude/Auth0 login is rejected, the next exact blocker will be whatever Auth0 callback/client-app setting the live login attempt names explicitly. That blocker is not currently evidenced from the GovMCP side.

7. STOP_BOUNDARIES

- Stopped after the live OIDC bring-up and public connector-surface verification.
- Did not fake a live Claude login from this environment.
- Did not modify repo code or store any secret material in repo paths.
