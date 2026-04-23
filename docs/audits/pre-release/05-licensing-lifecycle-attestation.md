## Code Review — Licensing Lifecycle & Attestation

### Scope
- Files reviewed: `mcp/licensing.py`, `mcp/server.py` (licensing + usage attestation paths), `dashboard/server.py` (licensing endpoints), `dashboard/ui-next/windows/licensing.js`, `dashboard/ui-next/licensing-api.js`, `dashboard/ui-next/tier-definitions.js`, `dashboard/ui-next/app.js`
- Design docs referenced: `/Volumes/SSD/archive/Gregs-dev-code/state/atested/licensing-app-design-capture-v3.md`, `/Volumes/SSD/archive/Gregs-dev-code/state/atested/product-design/tier-structure.md`, `/Volumes/SSD/archive/Gregs-dev-code/state/atested/product-design/license-signal-system.md`, `docs/INVARIANTS.md`, `docs/design/atested-v3-design.md`
- Tests examined: `tests/test_licensing.py`, `tests/test_usage_attestation.py`, `tests/test_notifications.py`

### Confirmed Working As Designed
- Licensing posture is evidentiary (not policy-enforcement coupled), with posture fields propagated onto governed records.
- License token verification path uses Ed25519 public-key verification and atomic license file persistence in `mcp/licensing.py`.
- Dashboard licensing endpoints persist key lifecycle events to the chain (registration/purchase/activation/renewal/downgrade events).

### Issues Found
| # | Severity | File:Line | Description | Design Reference |
|---|----------|-----------|-------------|-----------------|
| 1 | notable | `mcp/server.py:1801-1808`, `tests/test_usage_attestation.py:29-49` | Usage attestation still computes/validates legacy tier recommendations (`personal/team/business/enterprise`) rather than current model (`personal/personal_plus/crew/team/institution`). This is a design drift in both implementation and tests. | licensing-app v3 §5.1 lines 264-269; tier-structure.md tier model |
| 2 | notable | `dashboard/ui-next/windows/licensing.js:2897`, `dashboard/ui-next/windows/licensing.js:2915`, `dashboard/ui-next/windows/licensing.js:2934-2935` | Tier copy/ranges in licensing UI are off by one boundary: Team shown as `10–50` and Institution as `50+`; design requires Team `13–50` and Institution `51+`. | licensing-app v3 §5.1 lines 267-268 |
| 3 | notable | `dashboard/ui-next/licensing-api.js:5-7`, `dashboard/ui-next/licensing-api.js:15`, `dashboard/ui-next/licensing-api.js:23-27` | Licensing server integration module is still explicit phase-1 mock (`_BASE_URL = null`, not-ready responses), while design requires direct HTTPS licensing-server transaction path for purchase/renewal/registration flows and local chain event recording. | licensing-app v3 §2.4 lines 103-109; §2.5 lines 113-116; §11 |
| 4 | notable | `mcp/server.py:1834-1869`, `tests/test_usage_attestation.py::test_attestation_via_remote_server` | Runtime now requires signing for attestation artifacts unless `GOV_SIGNING_DEV_MODE=1`; test contract still expects unsigned success by default. This may be intentional hardening or a compatibility break. Marked needs clarification so tests and product contract align. | INV-005 (signing posture), needs clarification against test contract |
| 5 | critical | `mcp/server.py:1180-1236` (manifesting in `tests/test_licensing.py::test_posture_in_governed_records`) | Licensing posture integration test fails because governed call path crashes before returning JSON due `Path` serialization defect in normalized args (detailed in chunk 02). This currently blocks release baseline. | INV-001/INV-002/INV-004; cross-ref chunk 02 |

### Test Coverage Assessment
- Licensing/attestation tests are substantial and caught real integration regressions.
- Baseline currently includes two failing licensing-adjacent tests (`test_posture_in_governed_records`, `test_attestation_via_remote_server`).
- Coverage gap: no explicit tests enforcing new v3 tier boundaries in UI display strings.

### Observations
- Core licensing architecture is in place, but several surfaces still carry legacy tier semantics.
- The two failing tests are high-signal and should be resolved before release.
