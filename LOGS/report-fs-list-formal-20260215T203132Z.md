# FS_LIST Formalization Report

Timestamp (UTC): 20260215T203132Z

Change:
- Documented FS_LIST reason codes and precedence in docs/POLICY.md
- Added RC-FS-NOT-A-DIRECTORY and RC-FS-INCLUDE-HIDDEN-DISALLOWED to policy-eval.py
- Updated REASON_ORDER with FS_LIST-specific codes
- Added FS_LIST-specific checks for include_hidden and directory validation in policy-eval.py
- Updated mcp/server.py fs_list action to use operational errors (list_error) instead of policy reason codes
- Policy reasons now emitted only by policy-eval.py (separation of concerns)

Implementation details:
- Policy-eval.py checks include_hidden=False requirement (Phase 2 restriction)
- Policy-eval.py checks that target is a directory using os.path.isdir
- Tool action returns list_error for defense-in-depth (handles filesystem races)
- Clear separation: policy decisions from policy-eval, operational errors from tool action

Smoke output:
```
Processing request of type CallToolRequest
Processing request of type ListToolsRequest
Processing request of type CallToolRequest
Processing request of type CallToolRequest
Processing request of type ListToolsRequest
Processing request of type CallToolRequest
Processing request of type CallToolRequest
PASS: MCP smoke (DENY + ALLOW + tamper + fs_list tests passed, fail-closed verified)
```
