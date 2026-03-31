1. PURPOSE

Convert the public remote GovMCP OAuth/discovery contract from the prior same-origin/Auth0 hybrid model to a truthful direct-Auth0 model where Auth0 is the public authorization server and GovMCP remains only the protected resource.

2. BEFORE / AFTER CONTRACT MAP

Before:

- GovMCP served protected-resource metadata at `/.well-known/oauth-protected-resource/mcp`
- GovMCP also served same-origin:
  - `/.well-known/oauth-authorization-server`
  - `/.well-known/openid-configuration`
  - `/authorize`
  - `/token`
- those same-origin surfaces still declared Auth0 as issuer, creating a hybrid contract

After:

- GovMCP still serves protected-resource metadata at `/.well-known/oauth-protected-resource/mcp`
- protected-resource metadata remains:
  - `resource=https://mac-mini.tail341fb0.ts.net/mcp`
  - `authorization_servers=["https://dev-cizyho1vgel1c1g1.us.auth0.com/"]`
- GovMCP no longer presents itself as a public authorization server:
  - `/.well-known/oauth-authorization-server` -> `404`
  - `/.well-known/openid-configuration` -> `404`
  - `/authorize` -> `404`
  - `/token` -> `404`

3. IMPLEMENTATION

Changed files:

- `mcp/remote_server.py`
- `tests/test_mcp_remote_inspector_cors_allowlist.sh`
- `tests/test_mcp_remote_direct_auth0_contract.sh`

Bounded code seam:

- `_register_oidc_compatibility_routes()`

The same-origin authorization-server/OpenID metadata and `/authorize`/`/token` routes were neutralized so GovMCP no longer advertises a hybrid public auth contract.

4. PRESERVED BEHAVIOR

Preserved:

- canonical Auth0 audience expectation in `GOVMCP_OIDC_AUDIENCE`
- GovMCP protected-resource metadata compatibility from T441L
- bounded Inspector CORS allowlist from T441I on GovMCP-served surfaces
- pre-validation `/mcp` diagnostics from T441K
- `/mcp` resource-server token validation behavior

5. VERIFICATION

Focused verification:

- `tests/test_mcp_remote_direct_auth0_contract.sh`
- `tests/test_mcp_remote_protected_resource_metadata_alignment.sh`
- `tests/test_mcp_remote_inspector_cors_allowlist.sh`
- `tests/test_mcp_remote_prevalidation_auth_path_diagnostics.sh`

Verified:

- protected-resource metadata remains served by GovMCP and points clients to Auth0 as authorization server
- same-origin authorization-server/OpenID discovery endpoints are disabled
- same-origin `/authorize` and `/token` public routes are disabled
- protected-resource CORS behavior remains bounded
- pre-validation `/mcp` diagnostics still classify missing/malformed/bearer-present auth paths

6. DIAGNOSTICS / CORS STATUS

Preserved unchanged:

- Inspector CORS allowlist for `http://localhost:6274` on GovMCP-served surfaces that remain relevant
- `/mcp` pre-validation diagnostics

Intentionally removed as obsolete public contract surfaces:

- same-origin authorization-server/OpenID metadata
- same-origin `/authorize`
- same-origin `/token`

7. STOP_BOUNDARIES

This task does not change:

- Auth0 tenant configuration
- verifier audience/issuer semantics
- broader auth architecture beyond the direct-Auth0 public contract transition
