## Code Review — Operator UI Runtime

### Scope
- Files reviewed: `dashboard/ui-next/app.js`, `dashboard/ui-next/main-page.js`, `dashboard/ui-next/chrome.js`, `dashboard/ui-next/modal-manager.js`, `dashboard/ui-next/windows/activity.js`, `dashboard/ui-next/windows/audit.js`, `dashboard/ui-next/windows/record-detail.js`, `dashboard/ui-next/windows/alerts.js`, `dashboard/ui-next/windows/notifications.js`, `dashboard/ui-next/windows/identity-session.js`, `dashboard/server.py` (UI endpoints)
- Design docs referenced: `/Volumes/SSD/archive/Gregs-dev-code/state/atested/operator-ui-design-capture-v4.md`, `/Volumes/SSD/archive/Gregs-dev-code/state/atested/licensing-app-design-capture-v3.md`, `docs/INVARIANTS.md`
- Tests examined: `tests/test_dashboard_revamp.py`, `tests/test_notifications.py`, `tests/test_chain_health.py`, `tests/test_dashboard_autoreload.py`

### Confirmed Working As Designed
- Window model mechanics are implemented with depth-limited modal manager and child/grandchild navigation.
- Main-page recent feed routes to Activity and opens Record Detail as a grandchild (not direct child), matching v4 depth intent (`main-page.js` + `activity.js` + `record-detail.js` flow).
- Notification dismissal and viewed actions are chain-recorded via dashboard API endpoints (`dashboard/server.py` notification handlers).
- Targeted UI/backend tests passed: `45 passed` (`dashboard_revamp`, `notifications`, `chain_health`).

### Issues Found
| # | Severity | File:Line | Description | Design Reference |
|---|----------|-----------|-------------|-----------------|
| 1 | notable | `dashboard/ui-next/app.js:59-69`, `dashboard/ui-next/app.js:85-93`, `dashboard/ui-next/app.js:121-131` | First-run disclosure is not a pre-main-page gate: main page renders first, then disclosure check runs; endpoint failure skips disclosure entirely; copy is governance-event acknowledgment text rather than telemetry disclosure intent. Fix: block app interactivity until disclosure status resolves, fail closed on status-fetch error, and align copy to telemetry disclosure contract. | operator-ui v4 §4 lines 163-167; licensing-app v3 §4.2 lines 226-231 |
| 2 | notable | `dashboard/ui-next/app.js:11`, `dashboard/ui-next/app.js:49-52`, `dashboard/ui-next/windows/alerts.js:1-7`, `dashboard/ui-next/windows/alerts.js:118` | Chrome notification indicator opens Alerts window (tiered monitoring panes), not the Notifications history workflow. A Notifications implementation exists but is not wired as primary surface. This diverges from v4’s explicit notification indicator → Notifications window model. | operator-ui v4 §3.1 lines 102-104 and §5.8 lines 258-273 |
| 3 | notable | `dashboard/ui-next/app.js:183-187`, `dashboard/ui-next/windows/identity-session.js:156-175`, `dashboard/ui-next/windows/licensing.js:1718-1741`, `dashboard/ui-next/windows/licensing.js:2364-2411` | UI uses timer-driven polling/auto-refresh behavior (identity polling + licensing join/sharing polling). v4 technology constraints explicitly reject WebSocket/SSE/auto-refresh and require pull-based loads on page/open or explicit operator action. | operator-ui v4 §8 lines 390-392 |

### Test Coverage Assessment
- Strong regression coverage exists for dashboard rendering contracts and notification chain events.
- Coverage gap: no tests currently enforce v4 constraints around disclosure gating sequence and “no auto-refresh/polling” behavior.

### Observations
- The UI stack is functional, but multiple high-level UX/contracts from v4 have drifted.
- Most fixes are wiring/state-flow changes rather than deep architecture rewrites.
