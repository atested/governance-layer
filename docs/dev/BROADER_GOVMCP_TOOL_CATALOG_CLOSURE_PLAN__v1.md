# Broader GovMCP Tool-Catalog Closure Plan v1

## Closure target
Close the narrow MCP exposure seam for already-existing tool-catalog register/get/list/export/verify behavior.

## Minimum closure logic
1. Extend the `mcp/server.py` method allowlist and stdio dispatcher to recognize the tool-catalog MCP methods.
2. Add narrow server methods that:
   - reuse the existing `TOOL_REGISTER` capability module for register/get/list behavior
   - reuse the existing tool-catalog export/verify scripts for bundle behavior
3. Keep bundle storage under a bounded catalog-local root:
   - `out/mcp_tool_catalog_bundles`
4. Keep response shapes narrow and machine-readable so they match the existing system tests rather than inventing a new broad API layer.

## Constitutive surfaces
- `mcp/server.py`
- `mcp/capabilities/tool_catalog_module.py`
- `mcp/tool_catalog_store.py`
- `scripts/attest/export_tool_catalog_bundle.py`
- `scripts/attest/verify_tool_catalog_bundle.py`
- MCP-facing tool-catalog system tests

## Supporting but non-constitutive
- `mcp/README.md`
- broader tool-catalog report/slice semantics
- proof/export packaging beyond the selected catalog seam

## Explicit out of scope
- Broad `mcp/server.py` redesign
- GovMCP minimum-path rework
- GovMCP inspectability/query seam rework
- Tool-catalog ergonomics beyond register/get/list/export/verify exposure
- Generic connector cleanup

## Minimum implied implementation fronts
- Front A: method allowlist and dispatch closure
- Front B: register/get/list exposure closure through the existing capability module
- Front C: export/verify exposure closure through the existing tool-catalog scripts and canonical bundle root

## False broadening triggers
- Needing to redesign unrelated MCP methods
- Pulling proof/export bundle work into the seam by default
- Requiring a broad `mcp/server.py` rewrite instead of narrow method additions
