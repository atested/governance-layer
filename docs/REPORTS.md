# Reports

The Atested dashboard generates seven reports from the governance chain. Each
report provides a specific view of your operations. Reports are time-range
scoped and tier-restricted (see Tier Features for range limits).

## Governance Summary

**ID**: `governance-summary`

Shows what happened in the selected period: total decision counts (ALLOW and
DENY), which tools were used, and which policy rules were triggered. Start here
when you want a quick overview of governance activity.

**When to use**: Regular status checks, weekly reviews, or when you want a
single view of overall operations.

## Denial Patterns

**ID**: `denial-patterns`

Shows where policy is stopping risky activity. Breaks down denials by tool,
by rule, and by user. Useful for understanding which policies are active and
whether specific users or tools are generating repeated denials.

**When to use**: After a spike in denials, when tuning policy rules, or when
investigating whether a particular agent is operating outside its intended scope.

## User Comparison

**ID**: `operator-comparison`

Compares activity across user or agent identities. Shows decisions, tools used,
and rules triggered per operator. Each row represents one user identity with
aggregated metrics.

**When to use**: Multi-user environments where you want to compare workloads,
identify outliers, or verify that each user is operating within expected bounds.

## Audit Evidence Export

**ID**: `audit-evidence`

Generates an evidence summary for external review. Includes:

- Decision summary (ALLOW and DENY counts)
- Action breakdown by type
- Rules summary showing which rules were active
- Active approvals at the time of export
- Opaque actions paired with approval status

**Opaque action/approval pairing**: The report matches high-confidence
operations (Tier 3+) and explicit opaque invocation decisions against the
active approvals in the chain. Each action is shown with one of three statuses:

- Approved: an active approval covers this action (shows approving operator and date)
- Denied: no approval covers this action (or the approval expired)
- ALLOW without approval: the action was allowed but no matching approval exists (anomaly indicator)

This pairing gives auditors a clear view of which operations had explicit
operator authorization and which did not.

**When to use**: Preparing evidence for compliance reviews, audits, or when
sharing governance records with external parties.

## Unusual Activity Detection

**ID**: `unusual-activity`

Identifies events outside normal operating patterns. Shows anomalous tool
usage, hourly distribution patterns, and user activity spikes.

**When to use**: Investigating security incidents, validating that overnight
or off-hours activity is expected, or setting baseline behavior expectations.

## Telemetry Transparency

**ID**: `telemetry-summary`

Shows exactly what anonymous summary telemetry contains. Displays UI interaction
counts, governance usage aggregates, trouble submission totals, and system
health metrics. This is the same data visible in
`gov_runtime/LOGS/telemetry/summary.json`.

**When to use**: Before enabling telemetry, to verify what will be sent.
After enabling telemetry, to confirm what was actually transmitted.

## Support Requests

**ID**: `trouble-history`

Shows support requests previously submitted through the dashboard. Includes
priority breakdown and expandable details for each request including the
captured page context at time of submission.

**When to use**: Reviewing past support interactions, checking status of
submitted issues, or understanding what contextual information was included.

## Exporting Reports

All reports can be exported as JSON, CSV, or Excel. Export requires license-key
authentication. Every export is recorded in the governance chain with the report
name, format, time range, and record count. See Export Workflow for the full
process.
