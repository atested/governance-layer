1. PURPOSE

Add a strictly bounded diagnostic CORS allowlist for MCP Inspector origin `http://localhost:6274` so browser-based discovery/auth requests can reach the remote GovMCP endpoints needed for Inspector testing.

2. IMPLEMENTATION

Changed file:

- `mcp/remote_server.py`

Exact functions/helpers changed:

- `_DIAGNOSTIC_ALLOWED_CORS_ORIGINS`
- `_diagnostic_cors_allowed_origins()`
- `_wrap_with_diagnostic_cors()`
- `build_remote_app()`

3. ALLOWLIST SHAPE

The CORS allowlist is:

- constant-driven
- explicitly diagnostic-only

Allowed origin:

- `http://localhost:6274`

No wildcard origin and no localhost wildcard were added.

4. ENDPOINT SCOPE

The allowlist wraps the remote GovMCP app and therefore covers the browser-facing remote surface used by Inspector, including:

- `/.well-known/openid-configuration`
- `/.well-known/oauth-authorization-server`
- `/.well-known/oauth-protected-resource/mcp`
- `/mcp`
- `/authorize`
- `/token`

5. VERIFICATION

Focused coverage added in:

- `tests/test_mcp_remote_inspector_cors_allowlist.sh`

Verified:

- allowlisted Inspector origin receives `Access-Control-Allow-Origin`
- non-allowlisted origin does not receive `Access-Control-Allow-Origin`
- allowlisted Inspector preflight to `/mcp` succeeds

6. STOP_BOUNDARIES

This task does not widen token-validation policy, Auth0 configuration, or general production CORS posture beyond the explicit Inspector diagnostic origin.
