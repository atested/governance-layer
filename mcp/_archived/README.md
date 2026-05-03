# Governance MCP Broker (Phase 1)

This is a general-purpose MCP server that exposes governed tools (starting with `fs_write`).
It is **not OpenClaw-specific**. Any MCP client can connect.

## Runtime evidence (outside repo)
Runtime directory semantics:
- Set `GOV_RUNTIME_DIR=/absolute/path` to choose the runtime root explicitly.
- If unset, GovMCP now defaults to the repo-local runtime root `gov_runtime/`.
- The GovMCP required-path storage contract is intentionally multi-root:
  - receipts and receipt-to-tool-event link indexes are authoritative under `out/mcp_exec/`
  - tool-event indexes and bundles are authoritative under `$GOV_RUNTIME_DIR/TOOL_EVENTS/`
  - tool-catalog state remains supporting and authoritative under `out/mcp_tool_catalog/`

Runtime layout under `$GOV_RUNTIME_DIR`:
- `LOGS/decision-chain.jsonl` (append-only decision chain)
- `LOGS/intents/` (captured normalized intents)
- `LOGS/records/` (decision records)
- `LOGS/quarantine/` (quarantined broken chains + reason files)
- `TOOL_EVENTS/index.v1.json` (authoritative tool-event index for GovMCP required-path continuity)
- `TOOL_EVENTS/BUNDLES/` (tool-event bundle store)

Required-path state under `out/`:
- `out/mcp_exec/index.v1.json` (authoritative receipt index)
- `out/mcp_exec/<run_id>/action_record.json` (authoritative receipt/action record)
- `out/mcp_exec/tool_event_links.v1.json` (receipt-to-tool-event bridge index)
- `out/mcp_tool_catalog/` (supporting tool-catalog store; not a default blocker surface)

## Inspectability Contract

Broader GovMCP maturity beyond the landed minimum required path is bounded around a receipt-linked inspectability/query contract:

- constitutive surfaces:
  - `capabilities.receipt`
  - `capabilities.replay_check`
  - `capabilities.receipt_tool_events`
  - `capabilities.tool_event_receipts`
  - `capabilities.tool_event_list_for_receipt`
- partial surfaces:
  - `capabilities.list_recent`
  - `capabilities.tool_event_list_recent`

This keeps the seam focused on coherent receipt-linked inspection rather than broad connector redesign. Tool-catalog, bundle/export, and generic API cleanup remain supporting unless later evidence proves they are required.

## Install
Canonical venv location for this repo:
- mcp/.venv

Canonical interpreter for MCP smoke/tests:
- mcp/.venv/bin/python3

Create it from repo root:
- python3 -m venv mcp/.venv
- mcp/.venv/bin/python3 -m pip install -r mcp/requirements.txt

## Dependency pin note (`mcp==1.26.0`)
- Pin location: `mcp/requirements.txt` (`mcp==1.26.0`).
- Rationale: keep MCP client/server behavior deterministic across local runs and CI by using one known-good SDK version.
- Safe update procedure:
  1. Change only `mcp/requirements.txt` to the target version.
  2. Recreate or update the venv and reinstall dependencies.
  3. Run repo smoke/tests that exercise MCP paths (at minimum `tests/run-mcp-smoke.sh`).
  4. Document the version change and verification evidence in the task/PR.

## Smoke test (repo root, no manual venv activation)
- tests/run-mcp-smoke.sh

## Run (stdio)
- GOV_RUNTIME_DIR=/absolute/path/to/runtime mcp/.venv/bin/python3 mcp/server.py
- GOV_RUNTIME_DIR=/path/to/runtime python3 mcp/server.py
- python3 mcp/server.py  # defaults to repo-local gov_runtime/

## Run (remote foundation / streamable-http)
Dedicated remote-foundation entrypoint:
- `python3 mcp/remote_server.py`

Minimum runtime/config surface introduced by the remote foundation and auth/access tranches:
- `GOVMCP_REMOTE_AUTH_MODE`:
  - `bearer` (default)
  - `oidc`
- `GOVMCP_HOST`:
  - default `127.0.0.1`
- `GOVMCP_PORT`:
  - default `8000`
- `GOVMCP_STREAMABLE_HTTP_PATH`:
  - default `/mcp`
- `GOVMCP_LOG_LEVEL`:
  - default `INFO`
- `GOV_RUNTIME_DIR`:
  - same runtime-root contract as local stdio mode
- bearer-mode auth material, one of:
  - `GOVMCP_REMOTE_AUTH_TOKEN`
  - `GOVMCP_REMOTE_AUTH_TOKEN_FILE`
- oidc-mode issuer material:
  - `GOVMCP_OIDC_ISSUER_URL`
  - `GOVMCP_OIDC_AUDIENCE`
  - optional `GOVMCP_OIDC_REQUIRED_SCOPES`
  - optional `GOVMCP_OIDC_SIGNING_ALGORITHMS` (defaults to `RS256`)

Example local-only authenticated remote run:
- `GOVMCP_REMOTE_AUTH_TOKEN=change-me GOVMCP_HOST=127.0.0.1 GOVMCP_PORT=8000 python3 mcp/remote_server.py`

Remote auth/access scope note:
- transport boundary: `streamable-http`
- auth/access control:
  - `bearer` mode: shared bearer token, kept as a bounded transitional path for local/ops and non-connector remote use
  - `oidc` mode: external OIDC issuer token validation for connector-facing remote use
- connector compatibility surface in `oidc` mode:
  - same-origin authorization-server metadata:
    - `/.well-known/oauth-authorization-server`
    - `/.well-known/openid-configuration`
  - same-origin auth endpoints:
    - `/authorize` redirects to the configured external issuer authorization endpoint
    - `/token` proxies token exchanges to the configured external issuer token endpoint
  - same-origin authorization-server metadata explicitly advertises `token_endpoint_auth_methods_supported` including `none` so public-client / PKCE connector flows are not rejected at the metadata boundary
  - this compatibility shim keeps Auth0 or another configured issuer as the actual authorization authority
- deployment packaging and public exposure hardening: not configured in this tranche
- when `GOVMCP_PUBLIC_BASE_URL` is set for the deployment path, the remote streamable-http transport also admits that HTTPS host/origin in addition to localhost so proxied public requests do not fail host validation
- in `oidc` mode, `GOVMCP_PUBLIC_BASE_URL` is also used to publish protected-resource metadata for OAuth-capable remote clients

Print the effective remote foundation contract without starting the server:
- `python3 mcp/remote_server.py --print-config`

Fail-closed note:
- `mcp/remote_server.py` exits nonzero if the selected remote auth mode is not configured correctly.
- local stdio entrypoint `mcp/server.py` is unchanged and does not require remote auth settings.

## Run (deployment/startup contract)
Deployment helper entrypoint:
- `python3 mcp/remote_deploy.py`

Minimum additional deployment/startup surface:
- `GOVMCP_PUBLIC_BASE_URL`
  - required
  - must be an `https://` URL
  - defines the public client-facing base URL used to derive the remote MCP target

Deployment contract shape in this tranche:
- single-process authenticated GovMCP service
- local bind on `GOVMCP_HOST:GOVMCP_PORT`
- external HTTPS termination required outside this repo-scoped process
- public remote MCP URL:
  - `<GOVMCP_PUBLIC_BASE_URL><GOVMCP_STREAMABLE_HTTP_PATH>`

Print the deploy contract without starting the service:
- `python3 mcp/remote_deploy.py --print-contract`

Bounded operator guidance:
1. Provide runtime/config inputs:
   - if `GOVMCP_REMOTE_AUTH_MODE=bearer`:
     - `GOVMCP_REMOTE_AUTH_TOKEN` or `GOVMCP_REMOTE_AUTH_TOKEN_FILE`
   - if `GOVMCP_REMOTE_AUTH_MODE=oidc`:
     - `GOVMCP_OIDC_ISSUER_URL`
     - `GOVMCP_OIDC_AUDIENCE`
     - optional `GOVMCP_OIDC_REQUIRED_SCOPES`
   - `GOVMCP_PUBLIC_BASE_URL`
   - optional bind/runtime overrides such as `GOVMCP_HOST`, `GOVMCP_PORT`, `GOVMCP_STREAMABLE_HTTP_PATH`, `GOV_RUNTIME_DIR`
2. Start the service:
   - `python3 mcp/remote_deploy.py`
3. Point the remote Claude MCP client at:
   - the printed `public_mcp_url`
4. Auth shape:
   - `bearer` mode: direct bearer-token client support
   - `oidc` mode: OAuth/OIDC-capable clients discover the external issuer through the protected-resource metadata published by GovMCP

Truth boundary:
- this tranche does not provision TLS certificates, ingress, reverse proxies, or provider-specific hosting
- it assumes an external HTTPS termination layer exists at `GOVMCP_PUBLIC_BASE_URL`
- Auth0 may be used as the initial external issuer, but the GovMCP contract is issuer-oriented rather than Auth0-SDK-specific
- exact Claude UI steps vary by client surface and are outside this repo

## Tools
- fs_write: governed file write
