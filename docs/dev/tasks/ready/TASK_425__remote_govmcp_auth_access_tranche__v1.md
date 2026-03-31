# TASK_425__remote_govmcp_auth_access_tranche__v1

## 1. PURPOSE

Implement the minimum product-grade auth/access boundary for the remote GovMCP surface by requiring authenticated remote requests, rejecting unauthenticated access, and failing closed when remote auth is misconfigured.

## 2. SOURCE_PLAN_REFERENCE

Source plans:
- [TASK_423__product_grade_remote_govmcp_workfront_plan__v1.md](TASK_423__product_grade_remote_govmcp_workfront_plan__v1.md)
- [TASK_424__remote_govmcp_foundation_tranche__v1.md](TASK_424__remote_govmcp_foundation_tranche__v1.md)

This tranche follows the source plan's second phase while preserving the first tranche's boundary:
- keep local stdio unchanged
- keep the remote entrypoint explicit
- add only the minimum auth/access layer needed to make the remote surface non-open

## 3. AUTH_ACCESS_SCOPE

What this tranche adds:

- explicit bearer-token authentication for all remote GovMCP requests
- server-side request admission checks at the remote entrypoint
- fail-closed startup/config behavior when remote auth material is missing or invalid
- minimal runtime/config contract for supplying remote auth material

What this tranche does not add:

- user/account system
- multi-tenant auth model
- OAuth or identity-provider integration
- platform-specific secret management
- deployment packaging or public-exposure hardening

The bounded auth model in this tranche is:

- one shared bearer token for the remote GovMCP service boundary

## 4. IMPLEMENTATION

Concrete changes made:

- updated [mcp/remote_server.py](../../../../mcp/remote_server.py) to:
  - require remote auth configuration
  - load auth material from either `GOVMCP_REMOTE_AUTH_TOKEN` or `GOVMCP_REMOTE_AUTH_TOKEN_FILE`
  - reject conflicting or missing auth config
  - wrap the remote streamable-HTTP app with bearer-token admission checks
  - emit auth-related contract information through `--print-config`
- preserved [mcp/server.py](../../../../mcp/server.py) local stdio behavior unchanged
- updated [tests/run-mcp-remote-smoke.py](../../../../tests/run-mcp-remote-smoke.py) to verify:
  - unauthenticated remote access is rejected
  - invalid bearer token is rejected
  - correctly authenticated remote access succeeds in the bounded supported way
- added [tests/test_mcp_remote_auth_fail_closed.sh](../../../../tests/test_mcp_remote_auth_fail_closed.sh) to verify fail-closed auth misconfiguration behavior
- updated [mcp/README.md](../../../../mcp/README.md) so the remote path is documented as authenticated and fail-closed, while local stdio remains separate

## 5. AUTH_RUNTIME_CONFIG_CONTRACT

Minimum auth-related runtime/config surface introduced:

- `GOVMCP_REMOTE_AUTH_TOKEN`
  - inline bearer token for the remote service
- `GOVMCP_REMOTE_AUTH_TOKEN_FILE`
  - file path containing the bearer token

Rules:

- exactly one of those auth inputs must be provided for `mcp/remote_server.py`
- if both are provided, remote startup/config is invalid
- if neither is provided, remote startup/config is invalid
- local stdio entrypoint `mcp/server.py` does not consume or require those settings

Auth behavior:

- remote requests must present `Authorization: Bearer <token>`
- missing, empty, or incorrect bearer tokens are rejected
- remote auth is service-wide in this tranche, not per-user or per-tenant

## 6. VERIFICATION

Verification used:

1. local stdio path preserved
   - `bash tests/run-mcp-smoke.sh`
2. remote path rejects unauthenticated requests
   - `bash tests/run-mcp-remote-smoke.sh`
3. remote path rejects invalid bearer tokens
   - `bash tests/run-mcp-remote-smoke.sh`
4. remote path accepts correctly authenticated requests
   - `bash tests/run-mcp-remote-smoke.sh`
5. remote startup/config fails closed when auth is missing
   - `bash tests/test_mcp_remote_auth_fail_closed.sh`
6. docs/runtime wording remains truthful
   - repo-local inspection of [mcp/README.md](../../../../mcp/README.md)

## 7. OUT_OF_SCOPE

Still future tranches:

- deployment packaging and infrastructure
- public internet hardening beyond the bounded access layer
- mobile-client setup instructions
- OAuth or external identity-provider integration
- richer authorization model than one shared bearer token

This tranche only makes the remote surface authenticated and non-open.

## 8. STOP_BOUNDARIES

- stop before deployment/infrastructure work
- stop before identity-provider integration
- stop before multi-tenant or user-account auth design
- stop before widening local stdio behavior or altering the existing GovMCP capability surface
