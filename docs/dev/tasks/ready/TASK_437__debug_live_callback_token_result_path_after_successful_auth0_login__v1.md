1. PURPOSE

Determine the remaining post-login failure boundary after successful Auth0 authentication and implement the smallest truthful fix inside the live callback/token/result path without redesigning remote auth or replacing Auth0.

2. REPRODUCTION_RESULT

- Starting state on current main:
  - live GovMCP OIDC mode already worked at `https://mac-mini.tail341fb0.ts.net/mcp`
  - protected-resource metadata worked
  - same-origin authorization-server metadata worked
  - `/authorize` redirected to Auth0
- Observed user-facing failure remained:
  - Auth0 login succeeded
  - Claude still ended with: `Authorization with the MCP server failed`
- Repo-grounded public contract before the fix:
  - same-origin authorization-server metadata advertised only confidential-client token auth methods inherited from Auth0:
    - `client_secret_basic`
    - `client_secret_post`
    - `private_key_jwt`
    - `tls_client_auth`
    - `self_signed_tls_client_auth`
  - it did not advertise `none`
- Claude Help Center current guidance allows two connector modes:
  - optional static OAuth Client ID / Secret
  - otherwise Claude can operate against a remote OAuth server as a public client / DCR-driven client
- That meant the live same-origin metadata still encoded a token-step incompatibility even though the authorization step already succeeded.

3. CALLBACK_AND_TOKEN_FINDINGS

- `/token` is reachable on the live GovMCP origin:
  - bounded live probe:
    - `POST https://mac-mini.tail341fb0.ts.net/token`
    - with a bogus authorization-code payload and the real Auth0 client ID
  - result:
    - upstream Auth0 JSON error came back through the GovMCP shim:
      - `401`
      - `{"error":"access_denied","error_description":"Unauthorized"}`
- Therefore:
  - the live same-origin `/token` route exists
  - the request path can reach Auth0 through the GovMCP shim
  - a valid token was not returned in the bounded probe because the probe intentionally used a bogus authorization code
- The exact Claude-produced `/token` request from the failing live run was not directly observable from this environment without another fresh connector retry while instrumented.
- The post-login contract mismatch that was directly observable on current main was:
  - the same-origin authorization-server metadata did not advertise public-client token exchange support via `token_endpoint_auth_methods_supported=["none", ...]`

4. ROOT_CAUSE

The failing boundary was the authorization-server metadata contract at the callback/token step. GovMCP’s same-origin OAuth compatibility shim still advertised only confidential-client token auth methods even though Claude’s connector can operate as a public client or DCR-registered client after successful Auth0 login. That made the post-login token step incompatible at the metadata layer even though `/authorize` and `/token` were both present.

5. IMPLEMENTATION

- Updated `mcp/remote_server.py` so the same-origin authorization-server metadata now always includes:
  - `token_endpoint_auth_methods_supported` with `none` appended if the upstream issuer metadata does not advertise it
- Preserved:
  - Auth0 as the actual issuer
  - same-origin `/authorize` redirect behavior
  - same-origin `/token` proxy behavior
  - existing protected-resource metadata and OIDC token validation
- Updated regression coverage in:
  - `tests/test_mcp_remote_oidc_authorization_server_shim.sh`
- Updated operator/runtime wording in:
  - `mcp/README.md`

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

Live public verification after restart on patched code:

- protected-resource metadata still works:
  - `GET https://mac-mini.tail341fb0.ts.net/.well-known/oauth-protected-resource/mcp`
  - `200`
- same-origin authorization-server metadata now advertises public-client compatibility:
  - `GET https://mac-mini.tail341fb0.ts.net/.well-known/oauth-authorization-server`
  - includes:
    - `registration_endpoint=https://dev-cizyho1vgel1c1g1.us.auth0.com/oidc/register`
    - `token_endpoint_auth_methods_supported=[..., "none"]`
- `/authorize` still redirects to Auth0:
  - `307`
- unauthenticated `/mcp` still returns the expected OAuth challenge:
  - `401`
- bounded `/token` probe still reaches Auth0 through the shim and returns a standard upstream JSON error when the authorization code is invalid

End-to-end connector success:

- not directly re-verified from this environment in this task because that requires a fresh live Claude retry after the metadata fix

7. OUT_OF_SCOPE

- replacing Auth0 as issuer
- broader auth-provider redesign
- deeper identity or account-system work
- connector UI speculation beyond the bounded callback/token compatibility contract
- secret handling inside repo paths

8. STOP_BOUNDARIES

This tranche stops at the smallest truthful callback/token compatibility fix that could be localized from current-main behavior and live probing. If Claude still fails after this patch, the next bounded step requires observing one fresh live connector retry to capture the exact Claude-generated `/token` request and any subsequent authenticated `/mcp` call.
