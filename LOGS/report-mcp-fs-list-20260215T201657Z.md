# MCP FS_LIST Report

Timestamp (UTC): $(date -u +%Y%m%dT%H%M%SZ)

Change:
- Added FS_LIST capability to capability-registry.json (mirrors FS_WRITE allowlist)
- policy-eval.py already supports FS_LIST generically (no changes needed)
- Added MCP tool fs_list using governed_tool wrapper
- Extended MCP smoke test to cover fs_list ALLOW + hidden path DENY
- Adjusted chain growth expectation (+3 instead of +1)

Implementation details:
- fs_list tool uses same governed_tool pattern as fs_write
- Pre-checks for absolute path before governance
- Clamps max_entries between 1-500
- Action function denies include_hidden=True (Phase 2 restriction)
- Action function denies non-directory targets
- Filters out hidden entries (starting with ".")
- Returns entry names and types (file/dir/other)

Test coverage:
- ALLOW: list runtime/tmp directory, verify mcp-allow.txt is present
- DENY: attempt to list hidden directory (.hidden_test_dir)
- Chain integrity: verify 3 records added (1 fs_write + 2 fs_list)

Smoke output:
```
PASS: MCP smoke (DENY + ALLOW + tamper + fs_list tests passed, fail-closed verified)
```
