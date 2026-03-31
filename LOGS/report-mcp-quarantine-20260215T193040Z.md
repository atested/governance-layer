# MCP Quarantine Rotation Report

Timestamp (UTC): 20260215T193040Z

Change:
- On chain integrity failure, server quarantines decision-chain.jsonl instead of deleting it.
- Quarantined chains moved to runtime/LOGS/quarantine/ with timestamp.
- Evidence preserved for forensic analysis.
- Reason file written alongside each quarantined chain.
- Smoke test asserts:
  - Chain quarantined (original chain file moved)
  - Quarantine directory exists
  - At least one quarantined chain file present
  - ALLOW test succeeds with fresh chain after quarantine

Implementation:
- Added \_quarantine_chain() function in mcp/server.py
- Quarantine called on CHAIN_VERIFY_FAIL before raising RuntimeError
- Quarantine path included in error message
- Fixed deprecation warning: datetime.now(timezone.utc) instead of datetime.utcnow()

Smoke output:
```
Processing request of type CallToolRequest
Processing request of type ListToolsRequest
Processing request of type CallToolRequest
Processing request of type CallToolRequest
Processing request of type ListToolsRequest
PASS: MCP smoke (DENY + ALLOW + tamper test passed, fail-closed verified)
```
