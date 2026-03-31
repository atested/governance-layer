# TASK_424__remote_govmcp_foundation_tranche__v1

## 1. PURPOSE

Implement the remote foundation tranche for GovMCP by establishing a dedicated remote-serving boundary that is distinct from the existing local stdio path, while keeping auth and deployment hardening explicitly out of scope.

## 2. SOURCE_PLAN_REFERENCE

Source plan:
- [TASK_423__product_grade_remote_govmcp_workfront_plan__v1.md](TASK_423__product_grade_remote_govmcp_workfront_plan__v1.md)

This tranche follows the source plan's first phase:
- introduce the explicit remote server boundary
- establish the remote transport path
- keep the capability surface close to current main
- defer auth and deployment hardening

## 3. REMOTE_FOUNDATION_SCOPE

What counts as remote foundation in this tranche:

- a dedicated remote-serving entrypoint for GovMCP
- explicit separation between local stdio execution and remote-serving execution
- one bounded remote transport choice consistent with the product-grade target
- a minimum runtime/config contract for starting the remote service
- one bounded remote smoke path proving the remote service exists and is callable

What does not count as remote foundation in this tranche:

- product-grade auth/access control
- production deployment packaging
- public exposure hardening
- provider-specific hosting setup
- broader GovMCP capability redesign

## 4. IMPLEMENTATION

Concrete changes made:

- updated [mcp/server.py](../../../../mcp/server.py) so the MCP server is created with explicit env-driven runtime settings for host, port, log level, and streamable HTTP path
- added reusable server entry helpers in [mcp/server.py](../../../../mcp/server.py):
  - `run_local_stdio()`
  - `run_remote_streamable_http()`
  - `remote_runtime_contract()`
- preserved the existing local stdio default path in [mcp/server.py](../../../../mcp/server.py)
- added dedicated remote-serving entrypoint [mcp/remote_server.py](../../../../mcp/remote_server.py)
- added bounded remote smoke coverage:
  - [tests/run-mcp-remote-smoke.py](../../../../tests/run-mcp-remote-smoke.py)
  - [tests/run-mcp-remote-smoke.sh](../../../../tests/run-mcp-remote-smoke.sh)
- updated [mcp/README.md](../../../../mcp/README.md) to describe the remote-foundation contract truthfully without overstating auth/deployment readiness

Transport decision taken:

- `streamable-http`

Reason:

- it is directly supported by the pinned MCP SDK already in current main
- it aligns with the product-grade remote target better than extending stdio
- it avoids committing auth/deployment shape prematurely

## 5. RUNTIME_AND_CONFIG_CONTRACT

Minimum runtime/config surface introduced by this tranche:

- `GOVMCP_HOST`
  - default: `127.0.0.1`
- `GOVMCP_PORT`
  - default: `8000`
- `GOVMCP_STREAMABLE_HTTP_PATH`
  - default: `/mcp`
- `GOVMCP_LOG_LEVEL`
  - default: `INFO`
- `GOV_RUNTIME_DIR`
  - unchanged existing runtime-root contract

Bounded remote foundation contract:

- remote entrypoint: `python3 mcp/remote_server.py`
- transport: `streamable-http`
- local stdio entrypoint remains: `python3 mcp/server.py`
- `python3 mcp/remote_server.py --print-config` reports the effective remote foundation contract without starting the server

Truth boundary:

- auth/access is not configured in this tranche
- deployment packaging is not configured in this tranche
- the foundation is intended to create the remote-serving boundary, not complete remote readiness

## 6. VERIFICATION

Verification used:

1. local stdio path preserved
   - `bash tests/run-mcp-smoke.sh`
2. dedicated remote entrypoint exists and reports bounded contract
   - `python3 mcp/remote_server.py --print-config` via the remote smoke harness
3. remote-serving mode is callable in the intended shape
   - `bash tests/run-mcp-remote-smoke.sh`
4. docs/runtime wording remains truthful
   - repo-local inspection of [mcp/README.md](../../../../mcp/README.md) and the entrypoint/runtime contract

## 7. OUT_OF_SCOPE

Still future tranches:

- auth/access control
- deployment hardening and packaging
- mobile-client setup instructions
- public internet hardening
- broader remote UX polish

This tranche intentionally stops at the remote-serving boundary.

## 8. STOP_BOUNDARIES

- stop before auth implementation
- stop before deployment packaging
- stop before provider/hosting-specific setup
- stop before widening the GovMCP capability surface beyond the existing current-main shape
