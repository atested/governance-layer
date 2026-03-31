1. PURPOSE

Add a strictly bounded diagnostic-only dual-audience acceptance seam to the restored GovMCP OIDC token verifier so token validation can accept either the canonical Auth0 API audience or the Inspector MCP resource audience, while preserving signature, issuer, expiry, and scope checks.

2. IMPLEMENTATION

Changed file:

- `mcp/remote_server.py`

Exact verifier seam changed:

- `_OIDCTokenVerifier.__init__()`
- `_OIDCTokenVerifier._verify_sync()`

Supporting helpers added:

- `_DIAGNOSTIC_ALLOWED_AUDIENCES`
- `_diagnostic_allowed_audiences()`
- `_claim_audience_values()`
- `_match_allowed_audience()`

3. DIAGNOSTIC_ONLY_BOUNDARY

The new acceptance path is:

- constant-driven
- explicitly diagnostic-only

Accepted audiences are bounded to exactly:

- `https://govmcp.local/api`
- `https://mac-mini.tail341fb0.ts.net/mcp`

No other audience is accepted.

4. PRESERVED_VALIDATION

The change keeps existing JWT checks intact for:

- signature
- issuer
- expiry / time-based checks
- signing algorithm
- scope validation

Only the audience match moved from `jwt.decode(... audience=...)` to a bounded post-decode allowlist match after signature and issuer validation succeed.

5. VERIFICATION

Focused verifier-level coverage added in:

- `tests/test_mcp_remote_oidc_dual_audience_diagnostic.sh`

Verified outcomes:

- canonical audience accepted
- Inspector MCP resource audience accepted
- non-allowlisted audience rejected
- sanitized diagnostics emit which audience matched or that audience validation failed

6. STOP_BOUNDARIES

This task does not generalize audience acceptance beyond the two explicit diagnostic values and does not alter Auth0 configuration, OAuth flow shape, or any unrelated auth surface.
