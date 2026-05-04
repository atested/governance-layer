# Tier Features

Features available in each Atested plan. These are pulled from the running
code, not marketing materials.

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
removes the restriction.

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

Peer-to-peer sharing (adding additional machines) is available starting at
Personal Plus. The sharing machine runs a temporary HTTP server; the joining
machine connects via IP or UDP auto-discovery.

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
- **Personal Plus and above**: Multi-machine support, peer sharing
- **Crew and above**: Shared governance chain, multi-user governance, team activity view
- **Team and above**: Role-based governance, advanced reporting, access control
- **Institution**: Custom integrations, compliance reporting, enterprise analytics, dedicated support
