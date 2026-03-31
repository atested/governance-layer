# TASK_427__remote_govmcp_bringup_and_smoke_test__v1

## 1. PURPOSE

Record the actual repo-side and machine-side bring-up work performed for remote GovMCP, including local config materialization, localhost startup verification, authenticated request checks, and the remaining true external blocker for real remote/iOS use.

## 2. LOCAL_ENVIRONMENT_FINDINGS

Local environment findings from the current machine:

- repo baseline matched the requested current main
- [mcp/remote_deploy.py](../../../../mcp/remote_deploy.py), [mcp/remote_server.py](../../../../mcp/remote_server.py), and [mcp/README.md](../../../../mcp/README.md) were present
- system Python was available at `/usr/bin/python3`
- canonical MCP virtualenv was already present at `mcp/.venv/bin/python3`
- the deployment helper could print a valid contract once bounded local config was supplied
- the existing local stdio path remained usable during bring-up verification

## 3. CONFIG_MATERIALIZED

Bounded local config materialized for bring-up:

- generated one bearer token locally
- wrote it to a non-repo token file:
  - `/tmp/govmcp/remote_auth_token.txt`
- token file permissions were restricted to:
  - `0600`
- selected localhost bind port:
  - `51800`
- used bounded local config:
  - `GOVMCP_HOST=127.0.0.1`
  - `GOVMCP_PORT=51800`
  - `GOVMCP_STREAMABLE_HTTP_PATH=/mcp`
  - `GOVMCP_LOG_LEVEL=ERROR`
  - `GOV_RUNTIME_DIR=/Volumes/SSD/archive/gov/governance-layer/gov_runtime`
  - `GOVMCP_REMOTE_AUTH_TOKEN_FILE=/tmp/govmcp/remote_auth_token.txt`
  - `GOVMCP_PUBLIC_BASE_URL=https://govmcp-local.invalid`

Important truth note:

- `GOVMCP_PUBLIC_BASE_URL` was a bounded placeholder used only for local contract verification.
- It is not a real public remote URL.
- Raw secret value is intentionally not recorded here.

## 4. LOCAL_BRINGUP_RESULT

Bring-up result:

- `mcp/remote_deploy.py --print-contract` succeeded locally with the bounded config
- the authenticated remote GovMCP service was started successfully on localhost using:
  - `mcp/.venv/bin/python3 mcp/remote_deploy.py`
- the service was reachable at the local bind URL derived by the contract:
  - `http://127.0.0.1:51800/mcp`
- the service was then shut down cleanly after localhost verification completed

## 5. AUTH_AND_REQUEST_CHECKS

Localhost request checks against the running service:

- unauthenticated request:
  - rejected
  - observed result: `401 Unauthorized`
- invalid bearer token:
  - rejected
  - observed result: `401 Unauthorized`
- correct bearer token from the local token file:
  - accepted by the remote auth boundary
  - request reached the governed MCP tool surface successfully
  - bounded observed result was a truthful governed `DENY` response for an out-of-policy filesystem path, which is expected for the chosen smoke request

## 6. TRUE_EXTERNAL_BLOCKER

The one true blocker for actual Claude iOS / real remote use is:

**there is no real publicly reachable HTTPS URL yet that terminates externally and routes to this running GovMCP service, so the placeholder `GOVMCP_PUBLIC_BASE_URL` cannot be replaced with a truthful client-usable public MCP endpoint**

This is outside the repo and outside the bounded local bring-up task.

## 7. NEXT_OPERATOR_STEP

Minimum non-terminal action still needed from outside the repo:

- provide or provision one real public HTTPS endpoint that routes to this GovMCP process, then use that real URL as `GOVMCP_PUBLIC_BASE_URL` for the actual remote run and Claude client target

Nothing else in the repo is the primary blocker before that.

## 8. STOP_BOUNDARIES

- stop after bounded local bring-up and localhost auth verification
- stop before any DNS/TLS/ingress/provider provisioning not already available on the machine
- stop before any repo code changes
- stop at the first true external boundary for public remote use
