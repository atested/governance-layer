# FS_MKDIR Phase 2C.1 Report

Timestamp (UTC): 20260217T124500Z

## Changes

### capabilities/capability-registry.json
- Added FS_MKDIR entry: allow_base_dirs same as FS_WRITE/LIST/READ, deny_hidden_paths=true,
  deny_traversal=true, deny_overwrite_by_default=false (inapplicable).
  args: required=[path], optional=[parents, exist_ok].
  caps: parents_allowed=true, exist_ok_allowed=true.

### scripts/policy-eval.py
- Added FS_MKDIR branch to normalized_args block:
  norm["parents"] = bool(args.get("parents", False))
  norm["exist_ok"]  = bool(args.get("exist_ok", False))
- No additional capability-specific policy checks beyond shared path enforcement
  (allowlist, hidden, traversal). Existence state is a runtime concern.

### mcp/server.py
- normalize_args(): added FS_MKDIR branch — coerces parents + exist_ok to bool.
- fs_mkdir() governed tool: validates absolute path, builds intent, calls governed_tool().
  Action: canonical.mkdir(parents=..., exist_ok=...) using canonical path only.
  Operational errors: E-DIR-EXISTS, E-PARENT-NOT-FOUND, E-MKDIR-FAILED (runtime only).

### tests/run-mcp-smoke.py
- Added FS_MKDIR ALLOW test (creates mcp-mkdir-test under runtime/tmp).
- Added FS_MKDIR DENY test (path /tmp outside allowed roots).
- Chain growth updated from +5 to +7.

## Test results

### tests/test_fs_mkdir.sh
```
T-MKDIR-001 ALLOW: pass=9
T-MKDIR-002 DENY path: pass=5
T-POISON-MKDIR-001 cap_cfg: pass=6
T-POISON-MKDIR-002 argv steering: pass=5
Summary: pass=25 fail=0
```

### MCP smoke
```
PASS: MCP smoke (DENY + ALLOW + tamper + fs_list + fs_read + fs_mkdir tests passed, fail-closed verified)
```

## Regression

FS_WRITE: pass=12 fail=0
Poisoned intent: pass=14 fail=0
Canonical binding: pass=21 fail=0
Replay: pass=11 fail=0
