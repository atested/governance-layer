# Using the dashboard

The Atested dashboard is the operator's window into governance state. It shows what the proxy is doing, what decisions it has made, and what the operator can control. This page walks through each surface.

## Starting the dashboard

The dashboard launches alongside the proxy. Once running, open `http://localhost:<port>` in a browser. Authentication is handled automatically: a bearer token is generated at startup and embedded in the served page. No login form. No credentials to manage.

## The main page

The main page is what you see between workflows. It shows governance state at a glance: chain health, activity counts, verification state, machine role, and a feed of recent events. On a primary, it also shows connected remotes and version warnings. On a remote, it shows sync status, pending records, and approval/policy freshness.

**Chain health** shows the event count and chain integrity status. If the chain is intact, this is a green indicator. If a break has been detected, the indicator turns red and tells you where.

**Governance activity** gives you four numbers: mediated operations (total tool calls evaluated by policy), denied actions, approved operations, and approval-gated operations. These are your high-level signal for what the proxy is doing.

**Verification state** appears when certification data exists. It shows which governed surfaces have been certified, which are unverified, and whether drift has been detected.

**Recent activity feed** shows the last eight governance events. Each entry is clickable and takes you into the Activity view for that record.

## Activity

Activity is the chronological feed. Every governed event appears here: mediated decisions, approvals, revocations, verification changes, and imported remote records.

The table includes sequence number, timestamp, machine, event type, decision, summary, category, and a detail link. DENY rows get a red-tinted background.

Controls: date range filter, machine filter, column sorting, and pagination. Click any row to open the full record detail.

## Approvals

This is where you manage operator approvals for operations that policy denies.

The top section is the approval form. Enter a tool name, file path, or identity hash. Enter an operator name (defaults to "dashboard_operator" if you leave it blank). Click Approve.

Below the form, the currently approved operations table shows what has been approved, by whom, when, and with what scope. Each row has a Revoke button. Revoking asks for confirmation before proceeding.

When you encounter a DENY decision that you want to override, the Record Detail view for that decision includes an "Approve this operation" link that pre-fills the approval form with the right identifier.

## Audit

Audit is for searching the governance chain and verified imported remote sidecars. Filters include start time, end time, user identity, tool name, decision (ALLOW/DENY), event category, and machine.

Set your filters and click Search. Results appear in a table with sequence, time, event type, summary, user, and a detail link. Click any row to view the full record.

The Export JSON button at the bottom fetches up to 10,000 matching records and downloads them as a JSON file. The export includes metadata: export timestamp, query parameters, chain integrity status, and the matching records.

## Record Detail

Record Detail shows the full context of a single governance chain record. You reach it by clicking a row in Activity or Audit. Remote-originated records show a machine indicator with machine ID, event timestamp, and primary import timestamp.

The view adapts to the record type:

**Mediated decisions** show the ALLOW or DENY decision, tool name, target path, user, confidence tier, action type, scope, the policy rule that matched, denial reason (if DENY), verification state, and timestamp.

**Approval and revocation records** show the operation, operator, scope, context, and timestamp.

**Verification changes** show the surface name, previous state, new state, and timestamp.

Below the human-readable summary, the full chain record is displayed as JSON with a copy button. If a sidecar record exists, it appears in a separate section with its own copy button.

## Reports

Reports generates aggregate views of governance activity. Set a time range, machine scope, and grouping dimension (tool, user, machine, decision, or category), then click Generate.

The decision summary shows counts for each decision type. Below that, a horizontal bar chart breaks down the results by your chosen grouping. Each bar shows the label, a proportional fill, and the count.

## Health

Health shows infrastructure status for the governance system itself.

**Overall status** is a single indicator: Healthy, Attention, or Critical.

**Active alerts** appear when something needs attention. Each alert shows severity, source, message, and guidance. Alerts with acknowledgment controls let you record that you have seen them. The acknowledgment is written to the stability log.

**Chain integrity** shows whether the chain is intact, the record count, and verification status. If a break exists, you see the break location, reason, classification, and any auto-repair information.

**DENY rate trend** shows ALLOW and DENY counts, the DENY rate as a percentage, and whether an anomaly has been detected.

**Storage** shows chain size, stability log size, archive size, and archive count.

**License** shows the current license status, tier, trial days remaining (highlighted if under 7 days), and expiration timestamp.

**Machines** shows primary or remote role, connected remotes, per-remote sync status, version, pending records, and approval/policy freshness.

**Recent health events** lists stability log entries: auto-repairs, checkpoints, break detections.

## Configuration

Configuration lets you view and edit the capability registry and machine registry.

In view mode, you see the registry hash, integrity status, last verification time, and governed tool count. Below that, a table shows each governed tool with its risk level, allowed directories, and constraint flags (deny hidden paths, deny overwrite, deny executable outputs) plus hard caps.

To edit, enter your license key in the Unlock Editing form. After verification, the table becomes editable. You can add or remove directories for each tool, toggle constraint flags, and adjust hard caps. Save writes the changes. Cancel discards them.

Edit mode requires a valid license key. During the trial period, editing is restricted to paid license holders.

The machine registry shows the local machine ID, registry hash, authorized machines, license status, last sync time, and version for each remote.

## Feedback

Feedback has two purposes: submitting feedback to the Atested team and managing telemetry.

**Feedback form.** Write your feedback, optionally describe what Atested has helped you avoid or improve, choose whether Atested can use your feedback anonymously, and choose whether to send it to the Atested team via signed artifact. Submitted feedback is signed with your Ed25519 key.

**Telemetry controls.** Toggle anonymous usage data sharing on or off. The opt-in state is persisted. A "Send telemetry now" button triggers an immediate telemetry submission.

**History tables** show past feedback submissions and telemetry submissions with timestamps, content summaries, signing status, and content hashes.
