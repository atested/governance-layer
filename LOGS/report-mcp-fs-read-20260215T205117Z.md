# MCP FS_READ Report

Timestamp (UTC): 20260215T205117Z

Change:
- Added FS_READ capability with strict caps (max_bytes_default: 4096, max_bytes_hard: 65536).
- Added FS_READ policy codes and precedence in POLICY.md.
- Added RC-FS-NOT-A-FILE and RC-FS-MAX-BYTES-EXCEEDED to policy-eval.py.
- Implemented FS_READ-specific checks in policy-eval.py (max_bytes enforcement, file validation).
- Added MCP tool fs_read using governed_tool wrapper.
- Returns content (capped) with sha256 hash, supports text or base64 encoding.
- Extended smoke tests with fs_read ALLOW (read mcp-allow.txt) + hidden DENY; updated chain growth expectation to +5.

Implementation details:
- fs_read pre-checks absolute path, clamps max_bytes (1-65536), clamps offset (>=0)
- Policy-eval enforces max_bytes hard limit and validates target is a file
- Tool action handles operational errors (read failures, permissions)
- Content always includes content_hash_sha256 for integrity verification
- Supports both text (UTF-8 with error replacement) and binary (base64) modes

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
