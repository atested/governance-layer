## Code Review — MCP Governed Surface & Remote API

### Scope
- Files reviewed: `mcp/server.py`, `mcp/remote_server.py`, `mcp/v2_proxy.py`, `mcp/registry_integrity.py`, `mcp/capabilities/registry.py`, `mcp/licensing.py`, `mcp/storage_contract.py`
- Design docs referenced: `docs/design/atested-v3-design.md` (sections 3-5, 10), `docs/INVARIANTS.md` (INV-001, INV-002, INV-004, INV-006, INV-009, INV-010)
- Tests examined: `tests/test_api_evaluate_endpoint.py`, `tests/test_v2_proxy.py`, `tests/test_registry_integrity.py`, `tests/test_mcp_remote_*`

### Confirmed Working As Designed
- `/api/evaluate` implements unknown-tool auto-classification and persists learned mappings (`mcp/remote_server.py:844-860`, `mcp/remote_server.py:669-752`), consistent with INV-009.
- Registry integrity protection is fail-closed with schema validation, hash verification, and tamper detection (`mcp/registry_integrity.py` initialization + `verify_or_fail` path).
- Remote auth contract is explicit and fail-closed when bearer token config is missing in bearer mode (`mcp/remote_server.py:313-330`).
- Targeted MCP surface tests passed: `52 passed` (`test_api_evaluate_endpoint`, `test_v2_proxy`, `test_registry_integrity`).

### Issues Found
| # | Severity | File:Line | Description | Design Reference |
|---|----------|-----------|-------------|-----------------|
| 1 | critical | `mcp/server.py:1180-1196`, `mcp/server.py:1226-1236`, `scripts/policy_eval_shared.py:20-22` | `canonicalize()` returns `Path`, and `evaluate_and_execute_action()` stores those `Path` objects in `rec["normalized_args"]`. Hashing then JSON-serializes the record and fails (`Object of type PosixPath is not JSON serializable`). This breaks governed remote calls (reproduced via `fs_list`) and causes `tests/test_licensing.py::test_posture_in_governed_records` failure. Fix: normalize canonicalized values to `str` before inserting into records/args used for hashing. | `docs/design/atested-v3-design.md` §3 (govern before execution), INV-001/INV-002/INV-004 |
| 2 | notable | `mcp/server.py:1267-1290` | `evaluate_action()` still returns immediate DENY for unknown tools, while `/api/evaluate` path auto-classifies unknown tools first. Behavior is valid for current API route but creates split semantics if `evaluate_action` is called directly by future integrations. | INV-009 (needs consistent enforcement boundary) |

### Test Coverage Assessment
- Strong coverage exists for remote evaluate endpoint behavior and v2 proxy mediation.
- The critical `Path` serialization defect escaped targeted tests for hash recomputation in `evaluate_and_execute_action()` under real remote tool execution; add a focused regression test for canonicalized path fields in governed tool calls.

### Observations
- MCP surface architecture is mostly aligned to v3 and invariants.
- Primary release blocker in this chunk is the serialization defect, not policy logic.
