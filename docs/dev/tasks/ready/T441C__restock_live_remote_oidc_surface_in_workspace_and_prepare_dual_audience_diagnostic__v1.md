1. PURPOSE

Restock the live remote GovMCP OIDC runtime/auth surface from the archive runtime path into the writable Codex workspace without editing the archive repo, then identify the exact local audience-validation seam for a follow-on bounded dual-audience diagnostic.

2. ARCHIVE_SOURCE

Read-only source files used from `/Volumes/SSD/archive/gov/governance-layer`:

- `mcp/remote_server.py`
- `mcp/remote_deploy.py`

3. RESTOCK_SURFACE

Workspace files created:

- `mcp/remote_server.py`
- `mcp/remote_deploy.py`

Local compatibility seam added only inside the restocked `mcp/remote_server.py`:

- `_base_remote_runtime_contract()`
- `_apply_runtime_settings()`

These helpers let the restocked remote surface run against the existing workspace `mcp/server.py` without editing that file.

4. DRIFT_SUMMARY

Archive-only runtime/auth surface before restock:

- explicit remote deployment entrypoint
- explicit remote OIDC/bearer auth mode handling
- same-origin OAuth authorization-server compatibility routes
- OIDC token verifier and diagnostics

Workspace before restock:

- only local/stdout MCP surface in `mcp/server.py`
- no `mcp/remote_server.py`
- no `mcp/remote_deploy.py`

5. EXACT_AUTH_VALIDATION_SEAM

Primary token-validation file:

- `mcp/remote_server.py`

Primary audience/resource validation function:

- `_OIDCTokenVerifier._verify_sync()`

Exact audience check location:

- `jwt.decode(..., audience=self.audience, issuer=discovery.issuer, ...)`

Relevant surrounding diagnostic/rejection points:

- `_jwt_claim_preview()` for sanitized observed `aud`
- `_token_validation_failure_reason()` for rejection classification
- `_diagnostic_log("oidc_validation_failed", ...)`
- `_diagnostic_log("oidc_validation_passed", ...)`

6. FEASIBILITY_JUDGMENT

SAFE_LOCAL_CHANGE

Reason:

- after restock, audience validation is local to one verifier class in `mcp/remote_server.py`
- the current expected audience comes from one seam: `_oidc_audience()`
- the failure path is already instrumented and can emit explicit match/reject evidence without weakening issuer, signature, expiry, or scope checks

7. RECOMMENDED_NEXT_STEP

Apply the bounded dual-audience diagnostic only in `mcp/remote_server.py` by:

- introducing an explicit diagnostic-only accepted-audience allowlist containing exactly:
  - `https://govmcp.local/api`
  - `https://mac-mini.tail341fb0.ts.net/mcp`
- keeping issuer/signature/expiry/scope validation unchanged
- logging:
  - token presented
  - observed `aud`
  - matched audience
  - rejection reason when neither allowlisted audience matches
- adding focused tests for:
  - canonical audience accepted
  - MCP resource audience accepted
  - unrelated audience rejected

8. STOP_BOUNDARIES

This task did not implement the dual-audience change itself.

Reasons for stopping here:

- the restock needed to be made coherent in the workspace first
- the follow-on audience change is now clearly local and can be dispatched separately without touching the archive runtime or broadening auth policy silently
