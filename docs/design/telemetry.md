# Atested: Telemetry Layer

## Design — Aggregated Usage Reporting and Notification Delivery

**Date:** 2026-04-09
**Author:** Atested
**Status:** Design — pre-implementation
**Classification:** Architecture extension
**Companion docs:** [atested-v3-design.md](atested-v3-design.md) (v3 proxy architecture), [operator-identity.md](operator-identity.md) (operator identity and credential layer)

---

## 1. Purpose and Status

This document defines the telemetry layer for Atested: the mechanism by which
the dashboard reports aggregated usage data to atested.com and receives release
and advisory notifications in return.

The telemetry layer is independent of both the v3 proxy architecture
(atested-v3-design.md) and the operator identity layer (operator-identity.md).
Telemetry consumes chain data produced by the governance runtime but does not
modify governance behavior. It is not on the critical path for the operator
identity build sequence and may be built before, during, or after that work as
scheduling permits.

---

## 2. Problem Statement

Atested needs product telemetry for two reasons:

1. **Usage visibility.** The public-facing Approve/Deny counters on atested.com,
   product decisions, and adoption metrics all depend on aggregated usage data
   from deployed installs. This data is also the economic exchange that sustains
   the free tier.

2. **Outbound notifications.** Atested needs a channel to communicate release
   announcements, security advisories, and operational information to its
   installed base.

These are distinct concerns with different urgency and different audience
requirements. Telemetry is about Atested learning from its users. Notifications
are about Atested informing its users. This design treats them as separate
concerns that share some infrastructure.

Atested's positioning as a governance and integrity product imposes unusual
constraints on telemetry design. A product that markets cryptographically
verifiable governance cannot ship sloppy or surveillance-adjacent telemetry.
The telemetry mechanism must itself be governable, auditable, and transparent —
and the transparency mechanism is part of the product, not a hidden
implementation detail.

---

## 3. Design Principles

1. **Aggregated only.** Telemetry reports what kinds of things happened in
   aggregate, not what specifically happened. No content of decisions, no file
   paths, no tool call parameters, no tool names, nothing identifying.

2. **Content-free and path-free is architectural, not aspirational.** The
   aggregation layer physically cannot emit fields outside the published schema.

3. **The published schema is a contract.** The telemetry payload format is a
   documented public specification, versioned, published on atested.com. Changes
   to the schema require a version bump and a changelog entry.

4. **Dry-run inspectable.** The user can see exactly what the next telemetry
   payload will contain before it is sent, locally, without network access.

5. **Chain-documented.** Every telemetry transmission writes a
   proof-of-transmission event to the governance chain. The chain is the durable
   record of telemetry activity.

6. **Reconstructable, not stored.** Payload content is not separately archived
   on the user's machine. It is reconstructable on demand from chain-stored
   aggregated inputs via the historical formatter function, with fingerprint
   verification proving the reconstruction is accurate.

7. **Honest about the economic exchange.** Free tier defaults to telemetry-on
   because aggregated usage data is how the free tier is sustained. The opt-out
   exists and is documented, but is not featured in the main install flow. Paid
   tiers default to telemetry-on with prominent opt-out in dashboard settings.

8. **Notifications split by severity and purpose.** Security and critical
   non-security notifications reach every install regardless of telemetry status,
   because critical communications are a responsibility, not a reward. Routine
   and informational notifications ride the telemetry response channel, creating
   a real reciprocal benefit for telemetry participation.

---

## 4. Payload Schema (v1)

### Frequency

One payload per install per day.

For multi-machine installs, the "install" sender is the primary. Remotes never
transmit telemetry externally. They sync local summary counters to the primary,
and the primary builds one aggregate payload for the installation.

### Format

JSON. Published schema on atested.com with a version field. v1 is the first
version.

### Required fields

| Field | Type | Description |
|---|---|---|
| `schema_version` | integer | v1 = `1` |
| `atested_version` | string | Atested version string of the sending install |
| `platform` | string | OS platform identifier (`macos`, `windows`, `linux`) — no version detail, no architecture detail |
| `reporting_period_start` | string | ISO-8601 date, UTC |
| `reporting_period_end` | string | ISO-8601 date, UTC (typically start + 1 day) |
| `install_fingerprint` | string | SHA-256 prefix of a stable local identifier (license key fingerprint if licensed, randomly-generated install ID if unlicensed) |
| `licensed` | boolean | Whether the install is licensed or in trial state |
| `allow_count` | integer | ALLOW decisions in the reporting period |
| `deny_count` | integer | DENY decisions in the reporting period |
| `approval_count` | integer | Approval events (operator overrides of DENY) in the reporting period |
| `category_distribution` | object | Tool-call categories (from the classifier's category system — e.g., `file_read`, `file_write`, `network`, `command_execution`) mapped to counts. No specific tool names, no paths |
| `confidence_tier_distribution` | object | Classifier confidence tiers (`Tier 1` through `Tier 4`) mapped to counts |
| `rule_hit_distribution` | object | Policy rule identifiers (stable IDs from `capabilities/policy-rules.json`) mapped to counts. No rule content, just which rules fired and how often |
| `machine_coverage` | object | Aggregate machine coverage counts for multi-machine installs: total machines, reporting machines, stale/offline machines, and primary/remote counts. No hostnames or machine names |

### Excluded fields

The following are explicitly absent from the payload:

- Tool names, tool parameters, tool call arguments
- File paths, directory paths, URLs
- IP addresses, hostnames, machine names, user names
- Operator names or emails from the chain
- Content of denied operations
- Timestamps with resolution finer than one day
- Any free-text fields

Machine IDs are local governance identifiers. They are not included in external
telemetry payloads; telemetry uses counts only.

The aggregation layer is responsible for enforcing these exclusions. A telemetry
payload that contains a field not listed in the v1 schema is a schema violation
and must be rejected at construction time rather than sent.

---

## 5. Chain Documentation

Every telemetry transmission writes a proof-of-transmission event to the
governance chain. The chain event is not the outgoing payload itself — it is
the inputs plus a fingerprint of the formatted output.

### Chain event fields

| Field | Description |
|---|---|
| `event_type` | `"telemetry_send"` |
| `transmission_timestamp` | ISO-8601, UTC |
| `reporting_period_start` | Matching the payload |
| `reporting_period_end` | Matching the payload |
| `schema_version` | Matching the payload |
| `aggregated_inputs` | The full set of numerical inputs fed to the formatter: counts, distributions, version info — everything the payload was computed from |
| `payload_fingerprint` | SHA-256 of the exact bytes of the formatted outgoing JSON payload |
| `machine_coverage` | Machine coverage counts included in the outgoing payload |
| `http_status` | HTTP response status code from the telemetry endpoint |
| `http_response_fingerprint` | SHA-256 of the response body (proves what was received back, including any embedded notifications) |

The formatted outgoing payload is not separately stored anywhere. The chain
records the inputs and the fingerprint; the payload is reconstructable from
those inputs (see §6).

Historical formatter functions for every schema version must be retained in the
Atested codebase indefinitely. Adding a new schema version does not remove old
ones.

The chain event is written via the same INV-010 lock protocol as all other
chain writers.

---

## 6. Reconstruction and Local Inspection

### How reconstruction works

On demand, the dashboard or CLI can reconstruct any historical telemetry
payload by:

1. Reading the chain event's `aggregated_inputs` and `schema_version`.
2. Running those inputs through the historical formatter function for that
   schema version.
3. Verifying that the result hashes to the stored `payload_fingerprint`.

If the fingerprint matches, the reconstruction is proven accurate.
Reconstruction is a pure function of chain state plus the historical formatter.
No network access required. Users can audit their own telemetry history at any
time, offline.

### Dashboard

The dashboard exposes a Telemetry History view that lists every telemetry
transmission, showing: date, HTTP status, and reconstructed payload on demand.
Each historical entry surfaces a link to the published schema on atested.com
for the schema version of that payload, so users can verify that every field in
the reconstructed payload is covered by the schema.

### CLI

- `atested telemetry history` — lists all telemetry transmissions with dates
  and HTTP status codes.
- `atested telemetry show <date>` — reconstructs and displays the payload for
  a specific date.
- `atested telemetry preview` — shows what the next scheduled telemetry payload
  will contain, computed against the current chain state, without sending
  anything.

---

## 7. Opt-out

### Free tier

Telemetry is on by default. Opt-out is available via a documented environment
variable (`ATESTED_TELEMETRY=off`) or a single-line config file entry. The
opt-out is documented on atested.com in the product documentation. It is not
featured prominently in the main install flow or the quick-start guide. Users
who look for it will find it; users who don't won't be surprised by it either
(the install-time disclosure in §9 ensures awareness).

### Paid tiers

Telemetry is on by default. Opt-out is available in the dashboard settings UI
with a clear toggle. No subterfuge, no dark patterns — paid users can turn off
telemetry in one click from the settings page.

### What happens when telemetry is off

The dashboard writes no `telemetry_send` events to the chain and performs no
HTTP transmissions to the telemetry endpoint. Routine and informational
notifications that ride the telemetry response channel are unavailable. The
user can still check for updates manually via `atested version --check` or a
dashboard button. Security and critical notifications continue to reach the
install via the separate critical channel described in §8.

### Visibility

Opting out is never a silent operation. The dashboard header indicates
telemetry status (`telemetry: on` or `telemetry: off`) whenever the user is on
a settings-adjacent page. The chain records an opt-out event when telemetry is
first disabled on an install, so the audit trail is complete.

### No enforcement of telemetry

There is no attempt to prevent technical circumvention. Users who want to
disable telemetry by modifying source code or blocking the endpoint at the
firewall level can do so, and the design does not fight this. The opt-out path
is the supported path; circumvention is the user's choice and not Atested's
concern.

---

## 8. Notifications

### Channels

Notifications are delivered via two separate channels:

**Critical channel.** A lightweight polling endpoint at atested.com that returns
the current version, the severity of any updates the requesting install is
missing, and any active security or critical advisories. This endpoint is
polled by every Atested install once per day regardless of telemetry status.
Security and critical notifications always reach the install via this channel.

**Reciprocal channel.** The HTTP response body of the telemetry POST. When an
install sends telemetry, the response includes any pending routine or
informational notifications for that install. Telemetry-disabled installs do
not receive this channel.

### Severity levels

| Level | Meaning | Upgrade urgency |
|---|---|---|
| Security | A security fix is available | Recommended within 24–48 hours |
| Critical | An important non-security fix is available | Recommended soon |
| Routine | A new release with improvements and new features | No urgency |
| Informational | Minor updates, documentation changes, or non-release announcements | None |

### Dashboard banner behavior

| Level | Banner | Dismissal | Reappearance |
|---|---|---|---|
| Security | Red | Requires explicit acknowledgment ("I understand") | Reappears on next dashboard load if install not upgraded within 48 hours of first notification |
| Critical | Orange | Dismissable | Reappears daily until install is upgraded |
| Routine | Blue | Dismissable | Does not reappear unless user opens the updates page |
| Informational | Small passive indicator in header | Dismisses on click | None |

### CLI behavior

`atested version --check` queries the critical channel and reports any pending
notifications. Exit code is non-zero if security-level notifications are
pending, making the check suitable for scripting.

### General-purpose mechanism

The notification mechanism is not release-specific. It can carry software update
notifications, security advisories that aren't updates (e.g., "a policy rule in
the default ruleset has been deprecated"), licensing announcements, and
scheduled maintenance notices.

### Chain recording

All notifications received via either channel are recorded in the chain as
`notification_received` events, with timestamp, severity, and notification
content. This gives the user a full audit trail of what Atested communicated to
them and when.

---

## 9. Install-time Disclosure

During the first run of a newly-installed Atested instance, the dashboard
displays a one-time telemetry disclosure card: what is sent, what is not sent,
how often, and how to opt out. The user clicks through to continue.

The disclosure links to the published schema on atested.com and to the
documentation for the opt-out mechanism.

This disclosure is mandatory and non-dismissable until the user has read it.
The content is brief and factual, not a wall of legal text.

The first-run disclosure is recorded in the chain as a `disclosure_shown`
event.

---

## 10. Cadence and Failure Handling

### Transmission schedule

Telemetry sends occur once per day, anchored to UTC midnight with a small
random per-install jitter (up to ±30 minutes) to avoid all installs phoning
home at exactly the same time.

### Failure

If the telemetry endpoint is unreachable, the dashboard retries with
exponential backoff up to a retry cap. Persistent failure does not block any
Atested functionality.

### Batch on reconnect

If the dashboard is offline or not running at the scheduled transmission time,
the next run checks for missing days and sends a batch. The batch includes one
payload per missed day, each with its own chain event. The batch is capped at
30 days; older missed days are silently dropped (and a chain event is written
recording the drop).

### Dashboard-only

Telemetry is sent from the dashboard process only. The CLI does not send
telemetry independently. If the CLI is used headlessly on a server where the
dashboard never runs, no telemetry is sent from that install. This is an
accepted limitation.

### TLS and authentication

Telemetry endpoint TLS and authentication details are out of scope for this
design and will be specified during the build phase.

---

## 11. Honest Limits

- Telemetry depends on atested.com being reachable. Installs behind restrictive
  firewalls or air-gapped environments will not send telemetry. This is by
  design — telemetry is best-effort and never load-bearing.

- The `install_fingerprint` is stable per install, meaning atested.com can
  observe patterns from the same install across time. This is necessary for
  deduplication and for routine notifications to target specific installs. It is
  not an identity — atested.com cannot link an `install_fingerprint` to a human
  except through licensing data it already has (license key fingerprint for
  licensed installs).

- The aggregation layer is trusted. The design assumes that the aggregation code
  faithfully excludes content and paths from the payload. This is enforced by
  code review, testing, and the published schema contract, not by cryptographic
  mechanism. A compromised aggregation layer could theoretically emit additional
  fields, and the chain event's `payload_fingerprint` would prove that something
  was sent, but not necessarily what.

- The chain itself is verifiable. The aggregation layer is not. This is the
  honest limit of the design.

---

## 12. Positioning

The telemetry design is intended to be part of Atested's product story, not a
hidden implementation detail. "Here is what governed telemetry looks like" is a
concrete demonstration of the product philosophy.

The published schema, the dry-run preview, the chain documentation, the
reconstruction mechanism, and the severity-split notification channel are all
features that can be shown to prospective users. They are the product
demonstrating itself.

This positioning only works if the design is lived up to in implementation. A
telemetry mechanism that technically follows this design but ships additional
fields, uses the endpoint for non-documented purposes, or communicates outside
the documented channels would directly contradict Atested's core product claims.
The build sequence must treat telemetry implementation with the same rigor as
the governance chain itself.

---

## 13. Build Sequence (Informational)

This section is informational only. It describes the anticipated dispatch
sequence to implement this design. The actual dispatches are not authorized by
this document.

**T-1: Schema publication.** Publish the v1 schema on atested.com with a
versioned URL. Add schema change process documentation. No governance-layer
code yet. T-1 must land first — it is the public contract.

**T-2: Aggregation and formatter.** Implement the aggregation layer that
computes payload inputs from chain state, and the v1 formatter that produces
the outgoing JSON. Implement dry-run preview (`atested telemetry preview`).

**T-3: Chain event schema and writer.** Add `telemetry_send`,
`notification_received`, `opt_out`, and `disclosure_shown` event types to the
chain. Writer conforms to INV-010.

**T-4: Transmission, retry, and batch.** Implement the HTTP transmission layer,
retry logic, batch-on-reconnect, UTC anchoring with jitter.

**T-5: Telemetry history UI.** Dashboard and CLI views for telemetry history,
on-demand reconstruction, fingerprint verification.

**T-6: Notifications.** Implement the critical channel polling and the
reciprocal channel from telemetry responses. Implement the dashboard banner UI
for four severity levels.

**T-7: Install-time disclosure.** First-run disclosure card, chain event.

**T-8: End-to-end test pass.**

T-2 through T-7 can be sequenced or parallelized depending on the operating
mode at the time of the build. T-8 lands last.
