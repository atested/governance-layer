## Code Review — Dispatch Relay Service

### Scope
- Files reviewed: `services/dispatch-relay/server.py`, `services/dispatch-relay/com.governance.dispatch-relay.plist`
- Design docs referenced: `docs/INVARIANTS.md` (general auditability expectations), `/Volumes/SSD/archive/Gregs-dev-code/state/atested/product-design/launch-prerequisites.md` (operational infra posture)
- Tests examined: searched `tests/` and `system/tests/` for relay coverage (none found)

### Confirmed Working As Designed
- Service uses per-thread SQLite connections with WAL and busy timeout for concurrent operation.
- Dispatch lifecycle transitions (`pending -> claimed -> completed`) are guarded with conditional SQL updates, preventing double-claim and invalid completion transitions.
- Service binds to localhost by default (`uvicorn.run(... host="127.0.0.1")`).

### Issues Found
| # | Severity | File:Line | Description | Design Reference |
|---|----------|-----------|-------------|-----------------|
| 1 | critical | `services/dispatch-relay/server.py:204-205`, `services/dispatch-relay/server.py:227` | Auth middleware bypasses all authorization checks when `DISPATCH_BEARER_TOKEN` is unset; server explicitly starts in disabled-auth mode. This exposes write-capable dispatch mutation endpoints to any local caller and can be bridged by local compromise or port-forwarding mistakes. Fix: fail startup when token is missing (or require explicit `ALLOW_INSECURE_LOCAL=1` dev flag). | Security baseline; needs clarification in design docs |
| 2 | notable | `tests/:N/A`, `system/tests/:N/A` | No automated tests target dispatch-relay behavior (auth required/disabled mode, lifecycle race semantics, malformed payloads). | Launch-prerequisites operational hardening intent; needs clarification |

### Test Coverage Assessment
- No direct test coverage exists for this service in the current suite.
- Relay should have at least: auth enforcement tests, transition-state tests, and concurrent claim tests.

### Observations
- Core CRUD and transition logic is straightforward and readable.
- Main risk is permissive default auth posture plus absent coverage.
