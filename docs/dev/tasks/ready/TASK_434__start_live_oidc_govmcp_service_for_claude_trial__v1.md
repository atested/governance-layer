1. PURPOSE

Start GovMCP in live OIDC mode with the known Auth0 issuer and audience values, verify the public protected-resource metadata and unauthenticated `/mcp` behavior, and leave the service running for Greg to test from Claude.

2. LIVE_SERVICE_START_SUMMARY

Live OIDC service started with:

- `GOVMCP_REMOTE_AUTH_MODE=oidc`
- `GOVMCP_OIDC_ISSUER_URL=https://dev-cizyho1vgel1c1g1.us.auth0.com`
- `GOVMCP_OIDC_AUDIENCE=https://govmcp.local/api`
- `GOVMCP_PUBLIC_BASE_URL=https://mac-mini.tail341fb0.ts.net`
- `GOVMCP_HOST=127.0.0.1`
- `GOVMCP_PORT=6100`
- `GOVMCP_STREAMABLE_HTTP_PATH=/mcp`
- `GOVMCP_LOG_LEVEL=ERROR`
- `GOV_RUNTIME_DIR=/Volumes/SSD/archive/gov/governance-layer/gov_runtime`

Service entrypoint used:

- `mcp/.venv/bin/python3 mcp/remote_deploy.py`

Bounded run result:

- service started successfully
- local listener confirmed on:
  - `127.0.0.1:6100`

3. PUBLIC_METADATA_SUMMARY

Verified public protected-resource metadata over the live Funnel-backed URL:

- request:
  - `GET https://mac-mini.tail341fb0.ts.net/.well-known/oauth-protected-resource/mcp`
- result:
  - `200 OK`
- returned metadata:
  - `resource=https://mac-mini.tail341fb0.ts.net/mcp`
  - `authorization_servers=["https://dev-cizyho1vgel1c1g1.us.auth0.com/"]`
  - `bearer_methods_supported=["header"]`

4. PUBLIC_MCP_SUMMARY

Verified the public MCP path advertises auth-required behavior when unauthenticated:

- request:
  - `GET https://mac-mini.tail341fb0.ts.net/mcp`
- result:
  - `401`
- `WWW-Authenticate` header included:
  - `error="invalid_token"`
  - `error_description="Authentication required"`
  - `resource_metadata="https://mac-mini.tail341fb0.ts.net/.well-known/oauth-protected-resource/mcp"`

5. SERVICE_RUNNING_STATUS

Service was left running at the end of this task.

Observed running process:

- PID:
  - `16492`
- listener:
  - `127.0.0.1:6100`

6. FILES_CHANGED

- [TASK_434__start_live_oidc_govmcp_service_for_claude_trial__v1.md](/Volumes/SSD/archive/gov/governance-layer/docs/dev/tasks/ready/TASK_434__start_live_oidc_govmcp_service_for_claude_trial__v1.md)

7. REMOTE_PUBLICATION_STATUS

- branch publication recorded separately after writing this result artifact
