# Multi-Machine Governance Design Capture v2

Date: 2026-05-06
Source: Tier 0 design session + Codex independent review
Status: Reviewed, ready for spec

## Problem

Atested's paid tiers support multiple machines: Personal Plus supports 3 machines, Crew supports unlimited machines, and Team supports organizational use. The current product is single-machine. Without multi-machine support, there is no reason for a customer to buy anything above Personal.

## Integrity Model

The multi-machine architecture separates three distinct integrity layers. This separation keeps the integrity story clean and avoids making the primary chain do two incompatible jobs.

### Layer 1: Local Chain

Each machine writes its own per-machine governance log. This is the authoritative record of what happened on that machine. Each machine's chain is independently verifiable using that machine's signing key. This is exactly what exists today, extended with machine identity fields.

### Layer 2: Import Envelope

The primary chain records receipt and validation of remote material. When the primary receives records from a remote, it does not re-hash or mutate those remote records. Instead, the primary stores the remote material as received and appends an import envelope record to its own chain.

The envelope binds:

- Source machine identity.
- Remote record hash or archive manifest hash.
- Remote chain segment start and end hashes.
- Import sequence number.
- Primary `prev_record_hash`.
- Sync session id.
- Verification result.

This provides two guarantees:

- The remote chain remains independently verifiable with its original hashes and signatures.
- The primary chain proves it accepted that exact remote material at a specific point in primary history.

### Layer 3: Unified Report View

The unified view is a query layer that merges primary-local records and imported remote records for display. Reports, Activity, Walker, and evidence exports operate on this merged view. Filtering by machine, time range, decision type, and other criteria works against this layer.

The unified view is not a physical chain. Each underlying record retains its original integrity from Layer 1 or Layer 2.

## Architecture

### Local-First Governance

Every machine runs its own proxy and governs locally. Governance decisions happen with zero latency and zero dependency on other machines or network connectivity. Each machine writes to its own local chain.

### Machine Identity

Every machine gets a unique `machine_id` assigned during first-run setup. This includes the primary. Every chain record contains the `machine_id` of the machine that produced it.

Each machine has its own Ed25519 signing key generated during setup. The primary maintains an authorized machine registry containing:

- `machine_id`
- Public key fingerprint
- Role, either `primary` or `remote`
- License status
- First-seen timestamp
- Last-sync timestamp

### Primary And Remote Roles

The first machine in an installation is the primary. Additional machines are remotes.

The primary:

- Communicates with Atested's servers for telemetry, version checks, Communications, and license validation.
- Contains its own governance records plus import envelope records for remote material.
- Runs the sync service that remotes connect to.
- Holds the canonical approval store and distributes it to remotes.

Remotes talk only to the primary, never to Atested's servers.

## Sync Model

Remotes write locally, then sync to the primary.

### Sync Process

1. Remote connects to primary. Mutual authentication uses machine signing keys. Primary verifies the remote is in the authorized machine registry.
2. Remote sends unsynced archived records first. Archives include manifests signed by the remote. Primary verifies archive continuity: the previously imported remote tail hash must match the archive first record `prev_record_hash`.
3. Remote sends current unsynced chain records.
4. Primary verifies the remote material for hash linkage, signatures, and continuity from the last sync. Primary appends an import envelope record to its own chain binding the remote material. Remote records are stored as-is, not re-hashed.
5. Primary confirms receipt with the import envelope hash.
6. Primary sends back the current approval store with hash, policy rules with hash, pending Communications, product version information, and replicated state needed for restore.
7. Remote archives successfully synced records.
8. Remote continues with a fresh or trimmed local chain.

### Duplicate And Replay Protection

The sync protocol includes stable segment IDs or archive IDs. The primary can identify already-imported material without duplicating records. Remotes may retry after timeout without causing duplicate imports.

### Connectivity Gaps

If the remote cannot reach the primary:

- Governance continues locally.
- Local chain grows normally.
- If the local chain hits the size threshold, the remote archives locally with a signed manifest and marks archived records as unsynced.
- When connectivity returns, unsynced archives are sent first, then current records.
- The primary verifies archive continuity before import.
- `atested status` on the remote reports pending sync state, for example `47 records pending sync` or `all synced, last sync 2 minutes ago`.

## Record-Level Freshness

Every governance decision record includes:

- `approval_store_hash`: hash of the approval store version used for the decision.
- `policy_rules_hash`: hash of the policy rules used for the decision.

These fields let audits determine whether a remote acted before or after an approval revocation or policy update reached it.

## Policy And Approvals

Policy rules are shared from primary. All machines run the same policy. Remotes receive policy during sync and use their last-known policy between syncs. Each decision record binds the `policy_rules_hash` used.

Approvals are shared from primary. An approval made on the primary applies to all machines. Remotes receive the updated approval store during sync. An approval change triggers prompt sync so remotes converge quickly. Each decision record binds the `approval_store_hash` used.

Per-machine approvals are future work for geographically and functionally distributed setups.

## Remote Authorization

Licensing is the authorization mechanism. When a machine is added to the plan, that authorizes it as a remote. The remote discovers the primary's address during the licensing process.

Sync requires mutual authentication using machine signing keys. Licensing authorizes that a machine may join. The machine signing key authenticates that the sync peer is actually that machine during each sync. The primary also requires local operator confirmation before adding a remote key to the authorized machine registry.

## Telemetry

Remotes collect telemetry summaries locally. During sync, a remote sends telemetry data to the primary. The primary aggregates telemetry from all machines and sends one combined payload to Atested's servers. Only the primary transmits externally.

Under the chain event principle, the primary chain records the aggregated telemetry transmission with a payload hash. The Telemetry Transparency report on the primary shows what was sent across all machines.

Remotes do not transmit telemetry externally. Their telemetry data reaches Atested only through the primary.

## Communications

Atested's servers send Communications messages to the primary. During sync, the primary relays these messages to remotes. The operator sees messages on whichever machine they are using.

This accounts for the common scenario where the primary is a server and the operator's daily machine is a remote.

## Version Management

The primary checks for version updates via the version endpoint on `atested.com`. When a new version is available, the primary displays it in Communications and relays it to remotes during sync.

Each remote reports its version during sync. The primary tracks versions for all machines. If a remote is behind, the primary dashboard shows a warning. The operator updates each machine at their discretion.

If a remote's version is old enough that its record format or sync protocol is incompatible, the primary rejects the sync with a clear error directing the operator to update the remote. Record format changes should be additive whenever possible.

## Archiving

The primary archives normally per the existing auto-archive design.

Remotes archive after successful sync. The remote's archived records have already been accepted by the primary through import envelopes, so the remote local archive is a backup, not the primary record.

If a remote cannot sync and hits the size threshold, it archives locally with a signed manifest and marks the archive as unsynced. On reconnection, the primary verifies archive continuity before importing.

## Evidence Export

Evidence export works the same as today, with machine as an additional filter dimension alongside time range. The operator can export:

- All machines, using the unified view.
- A specific machine.
- A selected set of machines.

Records in the package include `machine_id` for attribution.

## Machine Removal

Removing a remote from the license revokes future sync authorization. It does not erase historical records. The primary's import envelopes for that machine remain in the chain as permanent history.

The removed machine may continue to govern locally in degraded or unlicensed mode. The product surfaces this state clearly to the operator on that machine.

## Primary Loss

For v1, supported recovery is primary restoration from backup. Full remote promotion is deferred.

Restore requires `gov_runtime` to contain enough replicated state:

- Approval store.
- Policy rules.
- Machine registry.
- Import envelope history and imported sidecars.
- License proof or cache.
- Signing key material.
- Integrity metadata and archive manifests.

## Operator Experience

### First Machine

`atested start` on a machine with no `gov_runtime`:

1. Setup flow creates runtime, generates signing key, configures base dirs, and assigns `machine_id`.
2. This is the first machine, so it becomes the primary automatically.
3. Proxy, dashboard, supervisor, and sync service start.

### Additional Machine

`atested start` on a new machine:

1. Setup flow creates runtime, generates signing key, configures base dirs, and assigns `machine_id`.
2. The operator chooses to join an existing installation and provides the primary address.
3. Remote registers with the primary. Authorization is through the license. The primary requires local operator confirmation before adding the remote public key to the authorized registry.
4. Proxy and supervisor start with sync configured to the primary.

### Dashboard

The primary dashboard shows the Layer 3 unified view across all machines. For v1, machine filtering is a search criterion in reports. Activity and Audit show all machines interleaved by default.

Reports distinguish `event_timestamp_utc`, when the event happened on the originating machine, from `primary_import_timestamp_utc`, when the primary recorded the import. This prevents the unified view from implying total chronological ordering that does not exist across machines.

### Status

`atested status` on the primary shows primary status plus all connected remotes: versions, last sync, record counts, health, and sync status.

`atested status` on a remote shows local governance status and sync status: connected state, last sync, pending records, approval store freshness, and policy freshness.

## Open Items For Implementation Detail

- Exact sync protocol transport and request signatures.
- Periodic sync frequency.
- Sync session ID generation and management.
- Discovery loss recovery.
- Primary restore procedure and backup validation tooling.
- State replication scope beyond approvals and policy.
- Exact `atested start` prompts.
- Network discovery versus manual address entry.
- Machine ID generation format.
- Sync service port and network requirements.
- Import envelope record schema.
- Unified report query implementation.
- UI details for machine representation and timestamp display.
- Degraded or unlicensed mode behavior.
