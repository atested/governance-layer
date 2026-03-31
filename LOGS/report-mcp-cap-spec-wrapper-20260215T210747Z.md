# MCP Capability Spec Driven Wrapper Report

Timestamp (UTC): 20260215T210747Z

Change:
- Added args and caps metadata to capability registry for FS_WRITE, FS_LIST, FS_READ
- governed_tool now normalizes args from capability registry and passes normalized args to action
- Tools rely on wrapper clamping and Phase disallowed flags
- Action signatures changed from (rec) to (rec, norm_args)
- Centralized arg normalization removes duplication across tools

Implementation details:
- Added CAP_REGISTRY_PATH constant and registry loading helpers
- normalize_args() function handles capability-specific arg clamping and validation
- Early return for missing required args
- FS_LIST: normalizes max_entries (1-500), enforces include_hidden=False
- FS_READ: normalizes max_bytes (1-65536), offset (>=0), as_text (bool)
- FS_WRITE: normalizes overwrite (bool), enforces request_executable=False
- Tool actions receive normalized args and use them directly
- No more local clamping logic in individual tools

Benefits:
- Single source of truth for arg normalization (capability registry)
- Consistent arg handling across all governed tools
- Easier to add new tools (just specify args/caps in registry)
- Phase restrictions centralized (include_hidden_allowed, request_executable_allowed)

Smoke output:
```
Processing request of type CallToolRequest
Processing request of type ListToolsRequest
Processing request of type CallToolRequest
Processing request of type CallToolRequest
Processing request of type ListToolsRequest
Processing request of type CallToolRequest
Processing request of type CallToolRequest
Processing request of type CallToolRequest
Processing request of type CallToolRequest
PASS: MCP smoke (DENY + ALLOW + tamper + fs_list + fs_read tests passed, fail-closed verified)
```
