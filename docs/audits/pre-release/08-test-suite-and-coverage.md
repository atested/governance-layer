## Code Review — Test Suite & Coverage Posture

### Scope
- Test surfaces reviewed: `tests/` Python + shell suites, `system/tests/` shell suites
- Baseline commands executed:
  - `python3 -m pytest tests/ -v`
  - `/Volumes/SSD/archive/gov/governance-layer/venv/bin/python -m pytest tests/ -v`
  - targeted component subsets for classifier/policy/proxy/dashboard/licensing
- Design docs referenced: `docs/INVARIANTS.md`, `/Volumes/SSD/archive/Gregs-dev-code/state/atested/product-design/launch-prerequisites.md`

### Confirmed Working As Designed
- In the project venv (Python 3.12), broad component subsets passed cleanly:
  - Core engine: `113 passed`
  - MCP surface: `52 passed`
  - Proxy/providers: `111 passed`
  - Dashboard/notifications/health: `45 passed`
- Full venv run outcome: `2 failed, 385 passed, 8 skipped` in `2.81s`.

### Issues Found
| # | Severity | File:Line | Description | Design Reference |
|---|----------|-----------|-------------|-----------------|
| 1 | critical | `tests/test_licensing.py::test_posture_in_governed_records`, `tests/test_usage_attestation.py::test_attestation_via_remote_server` | Release baseline is red in venv due two integration failures. One is a confirmed production bug (`Path` serialization in governed execution path), the other is attestation signing-contract mismatch requiring explicit decision. | INV-001/INV-002/INV-004/INV-005 |
| 2 | notable | `tests/test_api_evaluate_endpoint.py:35`, `tests/test_concurrent_chain_safety.py:20`, `tests/test_user_identity.py:21` | Exact requested baseline command with system `python3` (3.9) fails collection: unsupported union type syntax and `mcp.ClientSession` import mismatch. Test invocation is environment-sensitive and currently unreliable without venv pinning. | launch-prerequisites.md lines 118-119 (Python 3.9/MCP gaps) |
| 3 | notable | `tests/` and `system/tests/` suite composition | Requested baseline command covers Python tests under `tests/` only. It does not execute large shell-based regression suites in `tests/*.sh` and `system/tests/*.sh`, leaving significant release-gate/tooling contracts unvalidated if run alone. | INV-008, launch readiness expectations |
| 4 | notable | `services/dispatch-relay` coverage | No direct automated tests found for dispatch-relay auth/lifecycle behavior. | Cross-ref chunk 06 |

### Test Coverage Assessment
- Python unit/integration coverage is broad and high value.
- Coverage is fragmented across Python and shell harnesses; a single default command does not give full release confidence.
- Recommended release gate should include both Python venv run and selected shell/system contract suites.

### Observations
- The suite is strong but operationally inconsistent across interpreter environments.
- Test ergonomics should be tightened (single canonical pre-release command set with pinned interpreter).
