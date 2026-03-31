1. PURPOSE

Add strictly bounded sanitized diagnostics for `/mcp` requests so GovMCP can distinguish whether a request is rejected before OIDC validation because the Authorization header is missing, malformed, or whether the request proceeds into the validator.

2. IMPLEMENTATION

Changed file:

- `mcp/remote_server.py`

Exact functions/helpers changed:

- `_streamable_http_path()`
- `_request_targets_mcp()`
- `_prevalidation_auth_trace_fields()`
- `build_remote_app()`

3. DIAGNOSTIC SHAPE

The new diagnostics remain:

- config-driven through the existing `GOVMCP_OIDC_DIAGNOSTICS` gate
- explicitly diagnostic-only

Sanitized fields emitted:

- `authorization_header_present`
- `bearer_prefix_present`
- `bearer_token_extracted`
- `validator_entered`
- `rejection_stage`
- `rejection_reason`

No raw Authorization header values or token contents are logged.

4. VERIFICATION

Focused verification:

- `tests/test_mcp_remote_prevalidation_auth_path_diagnostics.sh`

Verified:

- missing Authorization header classified before validation
- malformed/non-Bearer header classified before validation
- bearer-present request classified as validator-entered
- existing validation failure logging still fires separately

5. AUTH BEHAVIOR

This task does not change accept/reject behavior. It only adds pre-validation classification ahead of the existing validator path.

6. STOP_BOUNDARIES

No CORS behavior, metadata behavior, audience expectations, issuer expectations, or token-validation semantics were changed.
