# Capability Registry Hash Binding Report

Timestamp (UTC): 20260216T103339Z

Change:
- policy-eval emits cap_registry_hash (sha256 of capability-registry.json bytes) in every decision record.
- verify-record enforces cap_registry_hash presence and exact match.
- FS_WRITE tests and MCP smoke assert the field exists.

FS_WRITE tests (tail):
```
PASS: T-FS-001 decision DENY (contains "policy_decision": "DENY")
PASS: T-FS-001 reason path disallowed (contains RC-FS-PATH-DISALLOWED)
PASS: T-FS-001 hash (record_hash verified)
PASS: T-FS-002 decision DENY (contains "policy_decision": "DENY")
PASS: T-FS-002 reason hidden path (contains RC-FS-HIDDEN-PATH)
PASS: T-FS-002 hash (record_hash verified)
PASS: T-FS-003 decision DENY (contains "policy_decision": "DENY")
PASS: T-FS-003 precedence traversal then hidden (order RC-FS-PATH-TRAVERSAL then RC-FS-HIDDEN-PATH)
PASS: T-FS-003 hash (record_hash verified)
PASS: T-FS-004 decision DENY (contains "policy_decision": "DENY")
PASS: T-FS-004 reason overwrite disallowed (contains RC-FS-OVERWRITE-DISALLOWED)
PASS: T-FS-004 hash (record_hash verified)

Summary: pass=12 fail=0
```

MCP smoke:
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
