1. PURPOSE

Align the served OAuth protected-resource metadata with the canonical Auth0 API audience contract so MCP clients discover the intended API audience instead of the `/mcp` endpoint URL.

2. IMPLEMENTATION

Changed file:

- `mcp/remote_server.py`

Exact helpers/routes changed:

- `_protected_resource_metadata_path()`
- `_protected_resource_metadata_payload()`
- `_register_oidc_compatibility_routes()`

3. CONTRACT CORRECTION

The metadata URL path remains:

- `/.well-known/oauth-protected-resource/mcp`

The served `resource` field is corrected to:

- `https://govmcp.local/api`

This keeps browser/client discovery pointed at the existing GovMCP metadata endpoint while aligning the advertised protected resource to the canonical API audience the verifier expects.

4. FIX SHAPE

The correction is:

- config-driven for the canonical audience value via `GOVMCP_OIDC_AUDIENCE`
- intended canonical correction, not a temporary wildcard or broadening change

5. CORS PRESERVATION

The T441I bounded Inspector allowlist remains in place:

- `http://localhost:6274`

No broader CORS expansion was introduced.

6. VERIFICATION

Focused verification:

- `tests/test_mcp_remote_protected_resource_metadata_alignment.sh`
- `tests/test_mcp_remote_inspector_cors_allowlist.sh`

Verified:

- served protected-resource metadata reports `resource=https://govmcp.local/api`
- allowlisted Inspector origin still receives CORS allow header
- non-allowlisted origin still does not receive CORS allow header

7. STOP_BOUNDARIES

This task does not redesign token validation, Auth0 settings, or broader OAuth metadata beyond the protected-resource document served at the existing GovMCP metadata path.
