# TASK_423__product_grade_remote_govmcp_workfront_plan__v1

## 1. PURPOSE

Define a bounded product-grade remote GovMCP workfront from current-main truth plus Greg's explicit decision that the target should be a real remote product surface, not an ad hoc extension of the current local-only stdio path.

## 2. CURRENT_MAIN_STARTING_POINT

Current main provides a functioning local GovMCP broker, not a product-grade remote service.

What already exists:

- [mcp/server.py](../../../../mcp/server.py) is the GovMCP entrypoint and exposes governed tools plus receipt-linked inspectability/query methods.
- [mcp/README.md](../../../../mcp/README.md) documents local runtime semantics, receipt/tool-event storage roots, dependency pinning, and stdio execution.
- [README.md](../../../../README.md) documents the MCP smoke/test setup and repo-local runtime/dependency assumptions.
- Runtime and evidence-oriented surfaces already exist:
  - `GOV_RUNTIME_DIR`
  - receipt store under `out/mcp_exec/`
  - tool-event store under `$GOV_RUNTIME_DIR/TOOL_EVENTS`
  - receipt signing helpers in [mcp/receipt_signing.py](../../../../mcp/receipt_signing.py)

What current main does not yet provide:

- an explicit remote HTTP-facing transport surface
- a remote-serving entrypoint distinct from local stdio invocation
- remote auth/access control
- deployment-facing configuration or operator guidance for exposing GovMCP to Claude clients

So the starting point is a real local broker with good governance-state surfaces, but without a remote product boundary.

## 3. PRODUCT_GRADE_REMOTE_TARGET

The intended remote target should be:

**an authenticated HTTPS GovMCP service with an explicit remote server entrypoint, a stable remote connection contract, and a deployment/config surface suitable for Claude mobile, web, and desktop clients**

That target is product-grade because it treats remote exposure as a first-class service boundary rather than as a thin wrapper around local stdio smoke behavior.

## 4. REQUIRED_REMOTE_CAPABILITIES

The product-grade remote target needs three distinct capability classes.

Transport:

- a real remote MCP transport over HTTPS rather than subprocess stdio
- a transport contract that is explicitly documented and intentionally supported as the remote path

Serving surface:

- a dedicated remote server entrypoint for GovMCP
- bounded runtime/config inputs for remote serving
- explicit service lifecycle assumptions such as bind/startup behavior and operator-visible configuration points

Client-usable connection shape:

- one remote GovMCP endpoint that Claude clients can connect to directly as a remote MCP server
- a connection model based on endpoint URL plus credential/config material, not repo-local process launch
- the same logical GovMCP capability surface across mobile, web, and desktop, even if client-side configuration differs outside this repo

## 5. AUTH_AND_ACCESS_REQUIREMENTS

Product-grade remote use requires a real auth/access layer before GovMCP should be treated as remotely deployable.

Minimum expectations:

- authenticated client access for the remote MCP endpoint
- explicit admission rules for who may call the remote service
- secret/credential configuration that is separate from receipt-signing material
- fail-closed behavior when auth configuration is missing or invalid
- clear separation between:
  - action/receipt signing for governance evidence
  - client authentication/authorization for remote service access

Current-main receipt signing can remain part of evidence integrity, but it is not the auth layer for remote exposure.

## 6. DEPLOYMENT_AND_CONFIGURATION_REQUIREMENTS

A product-grade remote GovMCP surface must also have an explicit deployment/config contract.

Minimum required deployment/config surface:

- a documented remote entrypoint and invocation model
- host/bind/runtime configuration for the remote service
- environment/config inputs for runtime root, signing, and remote auth
- a clear operator-facing statement of which artifacts remain local filesystem state versus which surface is externally exposed
- deployment guidance sufficient to stand up one remote GovMCP instance without relying on repo-internal smoke assumptions

This does not require full infra automation in the first tranche, but it does require the service boundary and configuration model to be explicit.

## 7. PHASED_IMPLEMENTATION_SHAPE

The smallest truthful sequencing that preserves product-grade direction is:

Phase 1: remote foundation tranche

- introduce the explicit remote server boundary
- establish the intended remote transport path
- separate local stdio execution from remote-serving execution
- define the remote connection contract at the service boundary
- keep the capability surface intentionally close to current main rather than widening scope

Phase 2: remote auth tranche

- add the product-grade auth/access mechanism for remote clients
- make remote startup fail closed when auth requirements are not satisfied
- document the credential/config model clearly enough for operators and clients

Phase 3: remote deployment tranche

- add the bounded deployment/operator configuration surface needed to run the authenticated remote service
- document the remote startup/deployment path and client connection expectations
- keep this focused on one deployable GovMCP instance, not broad hosting/platform generalization

Phase 4: deferred hardening after first remote usability

- operational hardening
- stronger deployment ergonomics
- broader observability/polish
- any additional remote-facing convenience layers proven necessary by actual use

This sequencing avoids local-to-remote patching that would later be thrown away, while still keeping the first implementation tranche bounded.

## 8. OUT_OF_SCOPE_FOR_FIRST_REMOTE_TRANCHE

The first remote tranche should explicitly exclude:

- broad GovMCP capability redesign
- tool-catalog maturity expansion beyond what the current capability surface already exposes
- multi-tenant or organization-scale access models
- advanced deployment automation or multi-environment packaging
- generalized public API polish unrelated to making one remote GovMCP service real
- doctrine or evidence-surface redesign not required for remote serving

The first tranche should create the remote service boundary, not solve every future remote-operability concern.

## 9. RECOMMENDED_NEXT_STEP

**PACKAGE_REMOTE_FOUNDATION_TRANCHE**

The next step should package the remote foundation tranche first, because current main is missing the remote service boundary itself. Auth and deployment work should follow that boundary, not precede it.
