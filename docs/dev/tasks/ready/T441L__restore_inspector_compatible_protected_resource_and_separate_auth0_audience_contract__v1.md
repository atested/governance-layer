1. PURPOSE

Restore Inspector-compatible OAuth protected-resource metadata while preserving the canonical Auth0 API audience contract through the existing runtime and verifier seam instead of the metadata `resource` field.

2. IMPLEMENTATION

Changed files:

- `mcp/remote_server.py`
- `tests/test_mcp_remote_protected_resource_metadata_alignment.sh`

Exact helpers changed:

- `_protected_resource_server_url()`
- `_protected_resource_metadata_payload()`

3. CONTRACT SEPARATION

Inspector-facing protected-resource metadata now serves:

- `resource=https://mac-mini.tail341fb0.ts.net/mcp`

The canonical Auth0 API audience remains separate and unchanged in:

- `GOVMCP_OIDC_AUDIENCE`
- `remote_runtime_contract()["auth_audience"]`
- `_OIDCTokenVerifier(... audience=_oidc_audience())`

4. FIX SHAPE

The correction is:

- intended canonical correction for the Inspector-facing protected-resource metadata
- config-driven for the canonical Auth0 audience contract
- not a token-validation policy change

5. PRESERVED BEHAVIOR

Preserved unchanged:

- T441I bounded Inspector CORS allowlist for `http://localhost:6274`
- T441K pre-validation `/mcp` auth-path diagnostics
- existing issuer/audience verifier configuration

6. VERIFICATION

Focused verification:

- `tests/test_mcp_remote_protected_resource_metadata_alignment.sh`
- `tests/test_mcp_remote_inspector_cors_allowlist.sh`
- `tests/test_mcp_remote_prevalidation_auth_path_diagnostics.sh`

Verified:

- protected-resource metadata is Inspector-compatible again
- canonical Auth0 audience still lives in the runtime auth contract
- allowlisted Inspector origin is still accepted
- non-allowlisted origin is still rejected
- pre-validation diagnostics still classify missing header, malformed header, and validator-entered paths

7. STOP_BOUNDARIES

This task does not redesign OAuth metadata broadly, change Auth0 settings, alter CORS scope beyond the existing bounded allowlist, or change token acceptance behavior.
