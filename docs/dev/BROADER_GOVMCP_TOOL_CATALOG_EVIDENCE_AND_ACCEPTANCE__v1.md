# Broader GovMCP Tool-Catalog Evidence And Acceptance v1

## Acceptance target
The selected tool-catalog seam is closed only if the existing tool-catalog register/get/list/export/verify behavior becomes available through narrow MCP methods without regressing already-landed GovMCP baselines.

## Required evidence
- Positive-path MCP proof:
  - `system/tests/test_mcp_tool_catalog_register_and_get.sh`
  - `system/tests/test_mcp_tool_catalog_list_recent.sh`
  - `system/tests/test_mcp_tool_catalog_export_bundle.sh`
  - `system/tests/test_mcp_tool_catalog_verify_bundle.sh`
- Baseline-preservation proof:
  - `tests/test_mcp_storage_contract.sh`
  - `tests/test_mcp_exposure_alignment.sh`
  - `tests/test_mcp_inspectability_contract.sh`

## Exact acceptance standard
The seam is closed only if:
1. the five tool-catalog MCP methods are recognized by the stdio server path
2. register/get/list responses are coherent with the existing tool-catalog store contract
3. export/verify responses are coherent with the existing tool-catalog bundle scripts
4. bundle export/verify works through the canonical catalog-local bundle root
5. already-landed GovMCP minimum-path and inspectability/query tests remain green

## False-closure cases
- Existing tool-catalog scripts work, but MCP methods still return `METHOD_MISMATCH`
- Register/get/list work, but export/verify is still absent
- Export works only through ad hoc paths rather than the canonical catalog-local bundle root
- Tool-catalog MCP methods work while already-landed GovMCP baselines regress
- Broad API cleanup is claimed as closure without passing the seam-specific MCP tests

## Result
This seam is acceptance-safe when the MCP surface becomes a narrow, test-backed exposure layer for already-existing tool-catalog behavior and nothing broader is claimed.
