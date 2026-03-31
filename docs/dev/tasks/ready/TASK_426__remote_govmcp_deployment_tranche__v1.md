# TASK_426__remote_govmcp_deployment_tranche__v1

## 1. PURPOSE

Implement the minimum deployment/startup/config tranche needed to run the authenticated remote GovMCP service in a truthful, deployable shape, while keeping broader hardening and provider-specific infrastructure out of scope.

## 2. SOURCE_PLAN_REFERENCE

Source plans:
- [TASK_423__product_grade_remote_govmcp_workfront_plan__v1.md](TASK_423__product_grade_remote_govmcp_workfront_plan__v1.md)
- [TASK_424__remote_govmcp_foundation_tranche__v1.md](TASK_424__remote_govmcp_foundation_tranche__v1.md)
- [TASK_425__remote_govmcp_auth_access_tranche__v1.md](TASK_425__remote_govmcp_auth_access_tranche__v1.md)

This tranche follows the intended sequence:
- foundation first
- auth second
- deployment/startup contract third

## 3. DEPLOYMENT_SCOPE

What this tranche adds:

- a dedicated deployment/startup helper for the authenticated remote GovMCP service
- explicit deployment/config validation for a client-facing HTTPS target URL
- a documented operator run shape for bringing up the authenticated service
- a bounded client-target contract describing which remote MCP URL Claude should use

What this tranche does not add:

- TLS certificate provisioning
- ingress/reverse-proxy automation
- provider-specific deployment manifests
- broader public-internet hardening
- richer auth or user/tenant models

The deployment shape added in this tranche is:

- single-process uvicorn-hosted GovMCP behind an external HTTPS termination layer

## 4. IMPLEMENTATION

Concrete changes made:

- exposed [mcp/remote_server.py](../../../../mcp/remote_server.py) remote app construction for reuse by the deployment helper
- added deployment/startup helper [mcp/remote_deploy.py](../../../../mcp/remote_deploy.py)
- the helper:
  - validates `GOVMCP_PUBLIC_BASE_URL`
  - requires that public base URL to be `https://`
  - derives the public client-facing MCP URL
  - preserves the already-landed auth/runtime settings
  - starts the authenticated remote app in the documented deployment shape
- added bounded deployment validation coverage:
  - [tests/test_mcp_remote_deploy_contract.sh](../../../../tests/test_mcp_remote_deploy_contract.sh)
  - [tests/run-mcp-remote-deploy-smoke.py](../../../../tests/run-mcp-remote-deploy-smoke.py)
  - [tests/run-mcp-remote-deploy-smoke.sh](../../../../tests/run-mcp-remote-deploy-smoke.sh)
- updated [mcp/README.md](../../../../mcp/README.md) to document the deployment/startup contract and bounded operator guidance

## 5. DEPLOYMENT_AND_CONFIG_CONTRACT

Minimum deployment/config surface in this tranche:

- existing remote auth/runtime inputs remain in force:
  - `GOVMCP_REMOTE_AUTH_TOKEN` or `GOVMCP_REMOTE_AUTH_TOKEN_FILE`
  - `GOVMCP_HOST`
  - `GOVMCP_PORT`
  - `GOVMCP_STREAMABLE_HTTP_PATH`
  - `GOVMCP_LOG_LEVEL`
  - `GOV_RUNTIME_DIR`
- new deployment-facing input:
  - `GOVMCP_PUBLIC_BASE_URL`

Rules:

- `GOVMCP_PUBLIC_BASE_URL` is required for the deployment helper
- it must be an `https://` URL
- the public remote MCP target is:
  - `<GOVMCP_PUBLIC_BASE_URL><GOVMCP_STREAMABLE_HTTP_PATH>`
- the locally bound service remains:
  - `http://<GOVMCP_HOST>:<GOVMCP_PORT><GOVMCP_STREAMABLE_HTTP_PATH>`

Truth boundary:

- this repo-scoped process does not terminate TLS itself
- external HTTPS termination is required outside the process
- this tranche defines the contract for that arrangement, not the surrounding infrastructure

## 6. OPERATOR_CONNECTION_GUIDANCE

Bounded operator/client model in this tranche:

1. Set the authenticated remote runtime inputs:
   - remote auth token or token file
   - public HTTPS base URL
   - optional bind/runtime overrides
2. Start the deployment helper:
   - `python3 mcp/remote_deploy.py`
3. Use the printed or derived `public_mcp_url` as the remote MCP target for Claude.
4. Supply the configured bearer token through the Claude client's remote MCP auth/header support.

Truthful scope note:

- this repo defines the server-side contract and the target URL shape
- exact Claude client UI steps vary outside the repo
- no claim is made that this tranche provisions or manages the external HTTPS layer

## 7. VERIFICATION

Verification used:

1. local stdio path preserved
   - `bash tests/run-mcp-smoke.sh`
2. deployment contract fails closed when required public URL is missing or invalid
   - `bash tests/test_mcp_remote_deploy_contract.sh`
3. documented auth/config inputs are sufficient to start the deployment helper
   - `bash tests/run-mcp-remote-deploy-smoke.sh`
4. deployment helper prints truthful contract metadata
   - `python3 mcp/remote_deploy.py --print-contract` through the contract test and deploy smoke
5. docs/runtime wording remains truthful
   - repo-local inspection of [mcp/README.md](../../../../mcp/README.md)

## 8. OUT_OF_SCOPE

Still future work:

- provider-specific deployment automation
- TLS certificate and ingress provisioning
- broader public-internet hardening
- multi-user or multi-tenant logic
- mobile-client UX specifics beyond the connection contract

This tranche only makes the remote authenticated service concretely runnable with a bounded deployment/startup contract.

## 9. STOP_BOUNDARIES

- stop before provider-specific infrastructure choices
- stop before broader hardening beyond the current auth boundary
- stop before any richer auth redesign
- stop before widening the remote deployment shape beyond one bounded service contract
