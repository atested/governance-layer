# GovMCP Required-Path Closure Post-Implementation Review v1

## Reviewed claim statement
Reviewed claim:

`The minimum GovMCP required-path blocker is materially closed on branch for the bounded path defined by the lane: explicit mixed-root storage contract, receipt -> retrieval -> replay linkage -> receipt-linked inspectability, and narrow exposure-layer alignment.`

## Review result
Result: `supported`

That support is for the bounded minimum-path claim only.

The review does not support any broader claim such as:
- broad GovMCP maturity
- general MCP server completeness
- tool-catalog closure as a constitutive blocker fix
- bundle/export maturity as constitutive blocker proof

## Why the claim is supported

### 1. Storage contract is explicit in implemented form
The new shared contract helper in `mcp/storage_contract.py` defines:
- runtime root
- receipt store root
- receipt index path
- tool-event store root
- tool-event link index path
- tool-catalog store root
- authoritative artifact ownership across runtime root vs `out/`

That contract is consumed by:
- `mcp/tool_event_store.py`
- `mcp/tool_catalog_store.py`
- `mcp/capability_introspection.py`
- `mcp/server.py`

This closes the earlier contradiction where:
- `mcp/server.py` defaulted to `/Volumes/SSD/archive/gov/runtime`
- `mcp/tool_event_store.py` defaulted to `repo_root/runtime`

### 2. Receipt-path continuity is materially closed
The implemented receipt path now has explicit continuity evidence for:
- receipt emission/indexing under `out/mcp_exec`
- receipt retrieval through `load_receipt()`
- replay linkage from retrieved receipt
- receipt-linked inspectability via tool-event digests

The implemented link-store getters also bridge mixed-root continuity narrowly rather than requiring a broad storage migration.

### 3. Exposure-layer changes remained narrow
`mcp/server.py` did not drift into a broad rewrite.

The server diff is bounded to:
- using the shared runtime-root resolver
- returning `storage_contract` metadata on receipt/replay/receipt-linked query surfaces
- returning `tool_event_digests` in failure-safe receipt/replay responses

The review did not find broad method redesign, feature expansion, or unrelated server refactors.

### 4. GovMCP / GovLayer-core / DevCore boundaries were preserved
- GovLayer-core trust-grade behavior remains a baseline dependency, not closure proof.
- DevCore process maturity is still non-counting.
- Tool-catalog and bundle/export surfaces remain supporting/non-constitutive.
- No reviewed change folded GovMCP closure back into GovLayer ownership.

## Contract/doc mismatch review
No material contract/doc mismatch was found inside the reviewed scope.

The implemented mixed-root contract in `mcp/storage_contract.py` matches the updated `mcp/README.md` on the key points:
- repo-local `gov_runtime/` default when `GOV_RUNTIME_DIR` is unset
- receipts and receipt/tool-event links under `out/mcp_exec`
- tool-event indexes and bundles under `$GOV_RUNTIME_DIR/TOOL_EVENTS`
- tool-catalog under `out/mcp_tool_catalog` as supporting state

## Boundary leakage / scope inflation review
No material boundary leakage was found.

### GovMCP / GovLayer-core
The branch did not count GovLayer-core replay/signing/verification as constitutive GovMCP closure proof.

### GovMCP / DevCore
The branch did not substitute workflow/runbook maturity for required-path continuity.

### Scope inflation
The branch did not silently widen the closure claim into:
- broad MCP readiness
- tool-catalog closure
- bundle/export closure
- broad `mcp/server.py` rewrite

## Test and evidence sufficiency review

### Positive-path evidence: strong
The targeted tests directly support the bounded claim:
- `tests/test_mcp_storage_contract.sh`
- `tests/test_mcp_receipt_tool_event_continuity.sh`
- `tests/test_mcp_exposure_alignment.sh`

Together they cover:
- explicit contract definition
- receipt emission/retrieval continuity
- replay linkage
- receipt-linked inspectability
- narrow exposure-layer alignment

### Residual evidence gap
There is still one bounded evidence gap relative to the full `TASK_374` acceptance model:
- no dedicated negative/false-closure test was added in this lane

That means the branch has strong positive-path proof, but not the full anti-inflation/negative-proof bundle described by the planning artifact.

Review judgment on this gap:
- it does not invalidate the bounded blocker-closure claim as currently stated
- it is a residual acceptance-strength gap, not a discovered logic mismatch

## Smoke harness review
Classification: `environmental`

Reason:
- `tests/run-mcp-smoke.sh` failed before exercising GovMCP logic
- `mcp/.venv/bin/python3` is absent in this environment
- importing `mcp` from system `python3` also fails

Observed review evidence:
- `VENV_PY=NO`
- `SYS_MCP_IMPORT=NO`

This indicates the smoke harness failure is due to missing local dependency/bootstrap state, not due to a demonstrated required-path regression.

Residual caution:
- because the smoke harness did not execute, it does not add end-to-end MCP client/server evidence for this branch in the current environment

## Minimal corrective patch review
No minimal corrective code or doc patch is required from this review.

Reason:
- no concrete overclaim or implementation/doc mismatch was found that requires narrowing
- the smoke-harness failure is environmental rather than a logic misalignment
- the residual missing negative-case proof is an evidence-strength note, not a discovered false statement in the reviewed branch outputs

## Merge readiness
Judgment: `safe as-is` for the bounded claim under review.

That safety is specifically:
- safe for merge as a bounded required-path closure lane result
- not a claim that broad GovMCP readiness is complete

Recommended merge note:
- retain the bounded wording
- note that MCP smoke was not exercised in this local environment because MCP client dependencies were absent
- treat explicit negative-case acceptance proof as follow-on evidence strengthening rather than pre-merge blocker, unless Cecil requires the full `TASK_374` acceptance bundle before merge

## Final review disposition
- Claim status: supported
- Contract/doc drift: none material
- Boundary leakage: none material
- Smoke harness: environmental failure, not demonstrated logic blocker
- Minimal corrective patch: not required
- Merge safety: yes, for the bounded claim only
