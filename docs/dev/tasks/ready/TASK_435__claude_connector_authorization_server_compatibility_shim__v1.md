1. PURPOSE

Implement the smallest bounded authorization-server compatibility layer needed for Claude's remote connector to complete OAuth discovery against GovMCP's public origin, while keeping Auth0 as the actual issuer and preserving the already-landed protected-resource metadata, Funnel path, and OIDC token-validation path.

2. REPRODUCTION_RESULT

- Current public GovMCP endpoint before the fix:
  - `https://mac-mini.tail341fb0.ts.net/mcp`
- Existing protected-resource metadata was already live and correct:
  - `resource=https://mac-mini.tail341fb0.ts.net/mcp`
  - `authorization_servers=["https://dev-cizyho1vgel1c1g1.us.auth0.com/"]`
- The connector-facing failure was reproducible on the GovMCP origin:
  - Claude iOS advanced the flow to `https://mac-mini.tail341fb0.ts.net/authorize?...`
  - that path returned `404 Not Found`
- Direct reproduction matched the observed behavior:
  - `GET /.well-known/oauth-authorization-server` on the GovMCP origin returned `404`
  - `GET /authorize?...` on the GovMCP origin returned `404`
- Local authenticated MCP calls still succeeded, so the gap was connector-facing auth discovery on the public origin rather than transport, Funnel, or OIDC token validation.

3. ROOT_CAUSE

Claude expected an authorization-server-facing surface on the GovMCP origin in addition to protected-resource metadata. Current main only published protected-resource metadata plus external-issuer token validation, but it did not expose same-origin authorization-server metadata or same-origin `/authorize` and `/token` endpoints. As a result, connector discovery bottomed out at `404 /authorize` on the GovMCP origin.

4. COMPATIBILITY_SCOPE

Added only the bounded compatibility surface needed for Claude-style same-origin auth discovery:

- same-origin authorization-server metadata:
  - `/.well-known/oauth-authorization-server`
  - `/.well-known/openid-configuration`
- same-origin authorization endpoint compatibility:
  - `GET /authorize` redirects to the configured issuer authorization endpoint
- same-origin token endpoint compatibility:
  - `POST /token` proxies token exchanges to the configured issuer token endpoint

Not added:

- local replacement of Auth0 as issuer
- broad OAuth provider redesign
- multi-tenant identity or user-account logic
- broader deployment or public-hardening changes

5. IMPLEMENTATION

- Updated `mcp/remote_server.py` to:
  - normalize issuer comparison so real Auth0 discovery with a trailing slash remains valid
  - fetch issuer discovery metadata once per process path as needed
  - register same-origin custom routes in `oidc` mode only
  - publish same-origin authorization-server metadata derived from the real issuer metadata while overriding `authorization_endpoint` and `token_endpoint` to GovMCP-origin compatibility routes
  - redirect `/authorize` requests to the real issuer authorization endpoint with the incoming query preserved
  - proxy `/token` requests to the real issuer token endpoint with bounded header passthrough
- Updated `mcp/README.md` so the connector-facing OIDC compatibility shim is documented truthfully.
- Added `tests/test_mcp_remote_oidc_authorization_server_shim.sh` to verify the new same-origin compatibility surface against a mock issuer.

6. VERIFICATION

Repo-local verification:

- `python3 -m py_compile mcp/remote_server.py mcp/remote_deploy.py`
  - `PASS`
- `bash tests/test_mcp_remote_oidc_fail_closed.sh`
  - `PASS`
- `bash tests/test_mcp_remote_oidc_auth.sh`
  - `PASS`
- `bash tests/test_mcp_remote_oidc_authorization_server_shim.sh`
  - `PASS`

Public/Funnel verification with live OIDC config:

- existing protected-resource metadata still works:
  - `GET https://mac-mini.tail341fb0.ts.net/.well-known/oauth-protected-resource/mcp`
  - `200 OK`
- missing authorization-server-facing surface now exists:
  - `GET https://mac-mini.tail341fb0.ts.net/.well-known/oauth-authorization-server`
  - `200 OK`
- connector-facing auth discovery path no longer bottoms out at `404 /authorize`:
  - `GET https://mac-mini.tail341fb0.ts.net/authorize?...`
  - `307 Redirect`
  - `Location: https://dev-cizyho1vgel1c1g1.us.auth0.com/authorize?...`
- local/remote OIDC validation behavior remains intact:
  - authenticated OIDC MCP smoke still reaches the governed tool surface successfully
  - unauthenticated `GET https://mac-mini.tail341fb0.ts.net/mcp`
  - still returns `401`
- no secret material was committed into repo paths

7. OUT_OF_SCOPE

- replacing Auth0 as the actual issuer
- deeper Auth0 SDK coupling
- broader OAuth or identity redesign
- deployment/provider redesign
- multi-user or tenant work
- mobile UI behavior beyond exposing the auth-discovery surface Claude requires

8. STOP_BOUNDARIES

This tranche stops at the bounded same-origin authorization-server compatibility shim. It does not redesign remote auth, replace the issuer, or broaden deployment and identity responsibilities beyond the minimum needed to stop Claude connector discovery from failing at `404 /authorize` on the GovMCP origin.
