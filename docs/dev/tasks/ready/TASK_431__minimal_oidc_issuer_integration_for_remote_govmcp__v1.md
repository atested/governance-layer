1. PURPOSE

Implement the minimum issuer-oriented OIDC/OAuth validation path needed for Claude-compatible remote GovMCP auth, using Auth0 as the initial external issuer choice while keeping the GovMCP side standards-based and minimally coupled.

2. CURRENT_MAIN_AUTH_BOUNDARY

Before this tranche, current main exposed only a shared bearer-token remote auth path:

- `GOVMCP_REMOTE_AUTH_TOKEN`
- `GOVMCP_REMOTE_AUTH_TOKEN_FILE`

That path worked for direct HTTP clients but was not sufficient for Claude connector use because the connector expects an OAuth-compatible remote auth surface rather than arbitrary manual bearer-token entry.

Decision input applied in this tranche:

- external issuer: selected
- Auth0: initial issuer choice
- GovMCP side: remain issuer-oriented and standards-based rather than Auth0-SDK-coupled

3. MINIMAL_OIDC_SCOPE

Added in this tranche:

- explicit remote auth mode selection:
  - `bearer`
  - `oidc`
- issuer-based access-token validation in `oidc` mode using:
  - OIDC discovery
  - JWKS lookup
  - JWT issuer/audience validation
- protected-resource metadata publication for the connector-facing MCP surface
- fail-closed startup/config validation when `oidc` mode is selected but issuer config is missing or invalid

Not added in this tranche:

- no local authorization server
- no client-registration system
- no redirect/approval UI
- no Auth0 SDK dependency
- no user/account system

4. IMPLEMENTATION

Concrete changes:

- updated [mcp/remote_server.py](/Volumes/SSD/archive/gov/governance-layer/mcp/remote_server.py)
  - added `GOVMCP_REMOTE_AUTH_MODE`
  - preserved existing bearer mode as an explicit transitional path
  - added OIDC-mode config validation
  - added issuer discovery plus JWKS-backed JWT verification
  - wired the pinned MCP SDK `TokenVerifier`/`AuthSettings` path so GovMCP now publishes protected-resource metadata and enforces issuer-based bearer validation in OIDC mode
- updated [mcp/remote_deploy.py](/Volumes/SSD/archive/gov/governance-layer/mcp/remote_deploy.py)
  - deployment contract now reports connector-facing auth requirements truthfully for bearer vs OIDC mode
- updated [mcp/README.md](/Volumes/SSD/archive/gov/governance-layer/mcp/README.md)
  - documents the issuer-oriented contract
  - states that Auth0 is only the initial issuer choice, not a code dependency
- added [tests/test_mcp_remote_oidc_auth.sh](/Volumes/SSD/archive/gov/governance-layer/tests/test_mcp_remote_oidc_auth.sh)
  - bounded local OIDC discovery/JWKS validation smoke
- added [tests/test_mcp_remote_oidc_fail_closed.sh](/Volumes/SSD/archive/gov/governance-layer/tests/test_mcp_remote_oidc_fail_closed.sh)
  - fail-closed coverage for missing issuer config

5. ISSUER_RUNTIME_CONFIG_CONTRACT

Minimum issuer-oriented runtime/config surface introduced:

- `GOVMCP_REMOTE_AUTH_MODE`
  - `bearer` (default)
  - `oidc`
- `GOVMCP_OIDC_ISSUER_URL`
  - required in `oidc` mode
  - initial real-world choice may be an Auth0 issuer URL
- `GOVMCP_OIDC_AUDIENCE`
  - required in `oidc` mode
- `GOVMCP_OIDC_REQUIRED_SCOPES`
  - optional space-separated scopes
- `GOVMCP_OIDC_SIGNING_ALGORITHMS`
  - optional
  - defaults to `RS256`
- `GOVMCP_PUBLIC_BASE_URL`
  - required in connector-facing OIDC deployment shape so GovMCP can publish truthful protected-resource metadata

Bearer-path handling:

- retained as a bounded transitional mode for local/ops and non-connector remote use
- no longer the only remote auth semantics exposed by GovMCP

6. VERIFICATION

Verification used:

- existing bearer-path remote smoke preserved:
  - `bash tests/run-mcp-remote-smoke.sh`
- new OIDC auth smoke:
  - `bash tests/test_mcp_remote_oidc_auth.sh`
  - verifies:
    - protected-resource metadata route exists
    - issuer-based validation path accepts a valid issuer JWT
    - no-auth rejects
    - wrong-token rejects
    - authenticated MCP call reaches the GovMCP surface
- fail-closed OIDC config:
  - `bash tests/test_mcp_remote_oidc_fail_closed.sh`
- no secret material committed into repo paths

7. OUT_OF_SCOPE

- deeper Auth0 coupling
- Auth0 SDK usage
- local authorization-server implementation
- dynamic client registration policy
- redirect/approval UX
- broader identity, tenancy, or RBAC design

8. STOP_BOUNDARIES

- Stopped after the bounded issuer-validation integration.
- Did not implement a local OAuth authorization server or broader identity system.
- Kept the GovMCP side issuer-oriented and minimally coupled to Auth0-specific concepts.
