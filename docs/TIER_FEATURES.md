# Tier Features

Features available in each Atested plan. The authoritative runtime registry is
`dashboard/ui-next/tier-feature-registry.json`; dashboard server behavior and UI
feature gates read from that registry.

## History Window

Controls how far back reports and activity views can query.

| Tier | Rolling History | Restricted Ranges |
|---|---|---|
| Personal | 10 days | 30-day and All Time unavailable |
| Personal Plus | 30 days | All Time unavailable |
| Crew | Unlimited | None |
| Team | Unlimited | None |
| Institution | Unlimited | None |

Selecting a restricted range shows a title bar message explaining which tier
removes the restriction. Custom report ranges beyond the rolling history window
are rejected by the dashboard server for Personal and Personal Plus.

## Reports

All seven reports are available on every tier. The time ranges they can cover
follow the history window above.

## Export Formats

All tiers support the same export formats:
- JSON
- CSV
- Excel

Export requires license-key authentication regardless of tier.

## Machine Cap

Controls how many machines can share a single license.

| Tier | Machines |
|---|---|
| Personal | 1 |
| Personal Plus | 3 |
| Crew | Unlimited |
| Team | Unlimited |
| Institution | Unlimited |

Multi-machine governance is available starting at Personal Plus. The first
machine is the primary. Additional machines join as remotes after license
authorization and local primary-side confirmation. Remotes govern locally,
write their own signed chains, and sync verified records to the primary.

## Communications Slots

Priority request capacity per billing period.

| Tier | Medium Priority | High Priority |
|---|---|---|
| Personal | 0 | 0 |
| Personal Plus | 2 | 0 |
| Crew | 4 | 2 |
| Team | 8 | 4 |
| Institution | 16 | 8 |

Medium-priority requests receive feedback-system response. High-priority
requests receive direct attention. Team and above include SLA-backed response
times. Institution slots include named support routing.

## Monitoring and Alerts

Alert panes unlock progressively by tier.

| Tier | Alert Pane | What It Covers |
|---|---|---|
| Personal | Safety Alerts | Chain integrity, security vulnerabilities, emergency notifications |
| Personal Plus | Operational Monitoring | DENY rate anomalies, chain health, version updates, stale approvals |
| Crew | Usage Pattern Detection | Cross-user denial patterns, classifier confidence shifts, unusual actions |
| Team | Governance Health | Compliance drift, policy analysis, unacknowledged alert follow-up |
| Institution | Continuous Oversight | Custom thresholds, scheduled reviews, named contact |

Each tier includes all panes from lower tiers.

## Governance Features

All tiers include:
- Governance chain (append-only, hash-linked, signed)
- Policy evaluation (classifier + rules)
- Dashboard access (all windows)
- Audit trail
- Evidence package export

Features that vary by tier:
- **Personal Plus and above**: Multi-machine support and machine-scoped reporting
- **Crew and above**: Unlimited machines, multi-user governance, team activity view
- **Team and above**: Role-based governance, advanced reporting, access control
- **Institution**: Custom integrations, compliance reporting, institutional analytics, dedicated support

## Registry Feature Flags

The runtime registry represents the same gates as feature flags:

| Feature Flag | First Active Tier |
|---|---|
| `governance_chain` | Personal |
| `policy_evaluation` | Personal |
| `dashboard_access` | Personal |
| `audit_trail` | Personal |
| `evidence_export` | Personal |
| `reports` | Personal |
| `multi_machine` | Personal Plus |
| `multi_user` | Crew |
| `shared_governance` | Crew |
| `team_activity` | Crew |
| `role_based_governance` | Team |
| `access_control` | Team |
| `advanced_reporting` | Team |
| `priority_feedback` | Team |
| `compliance_reporting` | Institution |
| `custom_integrations` | Institution |
| `dedicated_feedback` | Institution |
| `continuous_oversight` | Institution |
