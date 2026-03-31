# Broader GovMCP Tool-Catalog Seam Map v1

## Selected seam
Catalog-local MCP exposure coherence for already-existing tool-catalog store/query/export/verify behavior.

## Why this seam is selected
- Current main already has:
  - `mcp/tool_catalog_store.py` with deterministic `put`, `get`, `list_recent`, and `list_slice`
  - `scripts/attest/export_tool_catalog_bundle.py`
  - `scripts/attest/verify_tool_catalog_bundle.py`
  - existing MCP-facing system tests for register/get, list_recent, export bundle, and verify bundle
- Those MCP-facing tests currently fail with `FAIL:RPC_RC`, which traces to `CAPABILITIES_PROTOCOL_ERROR=METHOD_MISMATCH` in `mcp/server.py`.
- That makes the gap sharply bounded: the catalog behavior exists, but the MCP exposure contract for it does not.

## Baseline already landed
- GovLayer-core trust-grade closure
- GovMCP minimum required-path closure
- GovMCP inspectability/query seam closure
- Tool-catalog store root under `out/mcp_tool_catalog`
- Tool-catalog export/verify utilities and negative-path coverage below the MCP layer

## What remains thin / inconsistent / under-proven
- No narrow MCP methods for:
  - `capabilities.tool_register`
  - `capabilities.tool_get`
  - `capabilities.tool_list_recent`
  - `capabilities.tool_catalog_export_bundle`
  - `capabilities.tool_catalog_verify_bundle`
- Existing system tests already encode the expected MCP-facing contract, but main does not satisfy it.
- Tool-catalog maturity is therefore present below the MCP layer and thin at the exposure seam.

## Alternatives considered
### Tool-catalog query/report semantics
- Viable, but weaker as the immediate seam because core MCP method exposure is missing first.

### Tool-catalog export/verify hardening only
- Too narrow; export/verify already exist and the sharper current gap is MCP access to them.

### Broader `mcp/server.py` cleanup
- Too broad and unnecessary given the clearly bounded method-mismatch gap.

## Seam boundary
- Constitutive:
  - narrow MCP exposure for existing tool-catalog register/get/list/export/verify behavior
  - contract coherence between those MCP methods and the existing store/export/verify surfaces
- Supporting but non-constitutive:
  - broader tool-catalog query/report ergonomics
  - bundle/proof external-defensibility concerns
  - DevCore workflow/process maturity

## Result
The next sharply bounded broader GovMCP tool-catalog seam is the missing MCP exposure coherence layer for already-existing tool-catalog behavior.
