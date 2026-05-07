# Multi-Machine Governance Specification v1

Status: Implementation-ready
Date: 2026-05-06
Scope: Local-first multi-machine governance with primary aggregation, remote sync, unified reporting, and machine-aware evidence export.

## 1. Integrity Layers

Atested multi-machine governance has three layers.

### Layer 1: Local Chain

Each machine writes an independent local JSONL governance chain. Local records are authoritative for that machine and are verified with that machine's signing key.

### Layer 2: Import Envelope

The primary does not mutate or re-hash remote records. It stores remote material as received, verifies it, and appends a primary-chain import envelope that binds the remote segment by hash.

### Layer 3: Unified Report View

Reports query primary-local records plus imported remote records. This is a query and display layer, not a physical global chain.

## 2. Required Record Fields

Every governance record produced on any machine must include:

```json
{
  "machine_id": "machine_uuid_or_generated_id",
  "machine_role": "primary|remote",
  "event_timestamp_utc": "2026-05-06T12:00:00Z"
}
```

Every governance decision record must additionally include:

```json
{
  "policy_rules_hash": "sha256:...",
  "approval_store_hash": "sha256:..."
}
```

`timestamp_utc` may remain for backward compatibility, but new code should treat `event_timestamp_utc` as the originating machine event time.

## 3. Import Envelope Schema

Import envelopes are non-action governance events appended to the primary chain.

Canonical `event_type`: `remote_chain_import`

Required fields:

```json
{
  "record_version": "multi_machine_import_v1",
  "record_type": "non_action_event",
  "event_type": "remote_chain_import",
  "source_machine_id": "machine_id",
  "source_machine_key_id": "ed25519:sha256...",
  "source_machine_role": "remote",
  "segment_id": "sha256:...",
  "segment_kind": "current_chain|archive",
  "segment_format": "jsonl_segment_v1|archive_manifest_v1",
  "remote_first_record_hash": "sha256:...",
  "remote_last_record_hash": "sha256:...",
  "remote_record_count": 123,
  "previous_imported_remote_tail_hash": "sha256:...|null",
  "remote_manifest_hash": "sha256:...|null",
  "stored_segment_path": "imports/<machine_id>/<segment_id>.jsonl",
  "stored_segment_sha256": "sha256:...",
  "import_sequence": 42,
  "sync_session_id": "sync_...",
  "primary_import_timestamp_utc": "2026-05-06T12:03:00Z",
  "verification_result": "PASS|FAIL",
  "verification_errors": [],
  "prev_record_hash": "sha256:...",
  "record_hash": "sha256:...",
  "signature": "...",
  "signing_key_id": "ed25519:primary..."
}
```

`segment_id` is stable and idempotent:

```text
sha256(source_machine_id + "\0" + segment_kind + "\0" +
       remote_first_record_hash + "\0" + remote_last_record_hash + "\0" +
       remote_record_count + "\0" + stored_segment_sha256)
```

Failed imports may be recorded with `verification_result=FAIL`, but failed remote records must not enter the Layer 3 query set.

## 4. Machine Registry

The primary maintains a signed machine registry at:

```text
gov_runtime/machines/registry.json
```

Schema:

```json
{
  "registry_version": 1,
  "installation_id": "uuid",
  "machines": [
    {
      "machine_id": "uuid",
      "role": "primary|remote",
      "display_name": "operator label",
      "public_key_fingerprint": "ed25519:sha256...",
      "license_status": "active|removed|expired|revoked",
      "sync_authorized": true,
      "first_seen_utc": "2026-05-06T12:00:00Z",
      "last_sync_utc": "2026-05-06T12:03:00Z",
      "keys": [
        {
          "public_key_fingerprint": "ed25519:sha256...",
          "public_key_pem": "-----BEGIN PUBLIC KEY-----...",
          "valid_from_utc": "2026-05-06T12:00:00Z",
          "valid_until_utc": null,
          "revoked_utc": null
        }
      ]
    }
  ],
  "registry_hash": "sha256:..."
}
```

`registry_hash` is computed over canonical JSON with `registry_hash` set to `null`.

Registry changes must append primary-chain events:

- `machine_added`
- `machine_removed`
- `machine_role_changed`
- `machine_key_rotated`
- `machine_license_status_changed`

A remote is sync-authorized only if:

- `machine_id` exists in the registry.
- `sync_authorized=true`.
- `license_status=active`.
- Presented key fingerprint matches an active key validity window.
- Local operator confirmation was recorded during join.

Licensing grants entitlement. The primary still requires local operator confirmation before adding a remote key to the registry.

## 5. Remote Record Storage

Canonical imported storage is JSONL segment sidecars:

```text
gov_runtime/imports/<source_machine_id>/<segment_id>.jsonl
gov_runtime/imports/<source_machine_id>/<segment_id>.manifest.json
```

The import envelope binds the sidecar through `stored_segment_sha256`.

A SQLite index may be maintained for Layer 3 query performance:

```text
gov_runtime/imports/import_index.sqlite
```

The SQLite index is derived and rebuildable from sidecars plus import envelopes. It is not the integrity source.

## 6. Clock Semantics

Remote clocks are not trusted for integrity ordering.

Use:

- `event_timestamp_utc`: when the originating machine claims the event happened.
- `primary_import_timestamp_utc`: when the primary accepted the segment.
- `import_sequence`: primary-local ordering of imports.
- Remote chain linkage: authoritative ordering within a remote machine.

Reports must label both event time and import time when displaying remote records.

## 7. Key Rotation

Each machine key has a validity window. Registry entries must retain historical keys.

Verification uses the key valid at the record's `event_timestamp_utc`. If `event_timestamp_utc` is absent, verification uses the segment's declared event time range.

Key rotation process:

1. Machine generates a new Ed25519 key.
2. Primary authenticates the existing key.
3. Primary records `machine_key_rotated`.
4. Registry closes the old key validity window and opens the new one.
5. Future sync uses the new key.

Revoked keys cannot authorize new sync sessions, but historical records remain valid if signed during the key's valid window.

## 8. Sync Protocol

Transport for v1 is HTTP over the local network with mandatory app-level Ed25519 authentication and request signing. HTTPS is deferred as a future hardening option.

Rationale: the current product already runs plain HTTP locally, and v1 sync avoids certificate lifecycle complexity. App-level signatures authenticate machines, prevent request tampering, and support replay protection through nonces, session IDs, and segment IDs. HTTP does not provide confidentiality, so v1 sync treats the local network as operator-controlled. If confidentiality over hostile LANs becomes a requirement, add HTTPS, mTLS, Noise-style encrypted transport, or another encrypted app-layer session.

Session lifecycle:

1. Remote calls `POST /sync/v1/session/start`.
2. Primary returns `sync_session_id`, nonce, primary machine identity, supported protocol versions, and current primary registry hash.
3. Remote signs the nonce plus session metadata with its machine key.
4. Primary verifies registry authorization.
5. Remote sends segments in order: unsynced archives first, then current chain segment.
6. Every segment request is signed by the remote and includes `sync_session_id`, monotonic request number, segment ID, segment hash, and body hash.
7. Primary rejects stale session IDs, reused nonces, repeated request numbers, and segment ID/body hash conflicts.
8. Primary verifies each segment, writes the sidecar, appends an import envelope, and returns the import envelope hash.
9. Primary sends the remote state bundle: approval store, policy snapshot/hash, Communications, version info, and replicated registry metadata needed for restore.
10. Remote marks a segment synced only after receipt confirmation.

Transport security requirements for v1:

- HTTP is acceptable only because every sync request and response is signed at the application layer.
- Request signatures cover method, path, `sync_session_id`, request number, timestamp, body hash, and nonce-derived session binding.
- Responses from the primary are signed by the primary and verified by the remote.
- Confidentiality is not provided in v1 sync transport.
- Future hardening may add HTTPS, mTLS, or encrypted app-layer sessions.

Segment request:

```json
{
  "sync_session_id": "sync_...",
  "request_number": 3,
  "source_machine_id": "...",
  "segment_id": "sha256:...",
  "segment_kind": "archive|current_chain",
  "segment_sha256": "sha256:...",
  "records_jsonl_b64": "...",
  "archive_manifest": {},
  "remote_signature": "..."
}
```

Primary response:

```json
{
  "accepted": true,
  "segment_id": "sha256:...",
  "import_envelope_hash": "sha256:...",
  "approval_store": {},
  "approval_store_hash": "sha256:...",
  "policy_rules": {},
  "policy_rules_hash": "sha256:...",
  "communications": [],
  "version_info": {},
  "machine_registry_hash": "sha256:...",
  "primary_signature": "..."
}
```

Duplicate handling:

- Same `segment_id` and same bytes returns the existing import envelope hash.
- Same `segment_id` with different bytes is rejected as replay or tamper evidence.

Archive continuity verification:

```text
previous_imported_remote_tail_hash
  == archive first record prev_record_hash

archive internal linkage valid

archive tail hash
  == next current segment first record prev_record_hash
```

## 9. Sync Triggers

Required v1 triggers:

- Periodic baseline sync.
- Approval store change on primary.
- Communications message received on primary.
- Remote chain size threshold.
- Manual `atested sync`.
- Remote startup.
- Primary startup, to make the sync service available and refresh remote status as remotes reconnect.
- Product update or policy snapshot refresh.

Policy rules are not set by operators during normal operation. They change through product updates or bundled policy snapshot refreshes. After a product update changes bundled policy rules, the primary records the new `policy_rules_hash` and distributes the updated policy snapshot to remotes on their next sync. This is not an operator policy-edit trigger. If remotes are connected, the primary may request prompt sync so remotes converge quickly, but local governance continues using last-known policy until sync succeeds.

Default v1 interval: 5 minutes, configurable.

Failure backoff:

```text
30s -> 2m -> 5m -> baseline interval
```

Approval changes request prompt sync because they reflect operator intent. Policy hash changes caused by product updates are surfaced as version and policy freshness state, not treated as ordinary operator configuration changes.

## 10. Machine Removal

Removing a machine:

- Sets `license_status=removed`.
- Sets `sync_authorized=false`.
- Appends `machine_removed`.
- Preserves all historical import envelopes and sidecars.

A removed remote may continue local governance in degraded or unlicensed mode. It must show clear status, stop syncing, and mark records as local-only or unlicensed until reauthorized.

## 11. Primary Restore

Full remote promotion is deferred for v1. Supported v1 recovery is restore primary from backup.

Required `gov_runtime` state for restore:

```text
LOGS/decision-chain.jsonl
imports/
machines/registry.json
approvals/
capabilities/policy-rules.json or policy snapshot
communications/
telemetry/
license proof/cache
signing key material
integrity metadata and archive manifests
```

Restore procedure:

1. Install Atested on replacement primary.
2. Restore `gov_runtime`.
3. Run integrity verification.
4. Start primary sync service.
5. Remotes reconnect using existing primary identity if key material was restored.
6. If primary key changed, operator must explicitly re-pair remotes.

## 12. Operator Experience

Primary first start:

```text
atested start
```

The command:

- Creates runtime.
- Generates machine ID and signing key.
- Sets role `primary`.
- Creates machine registry.
- Starts proxy, dashboard, supervisor, and sync service.

Remote start:

```text
atested start
```

The command:

- Creates runtime.
- Generates machine ID and signing key.
- Asks whether to join an existing installation.
- Accepts primary address from the operator.
- Presents license authorization and public key to the primary.
- Requires primary-side local operator confirmation before registry add.
- Starts proxy and supervisor with sync enabled.

`atested status` on primary shows:

- Primary health.
- Sync service status.
- Machine list.
- Last sync per remote.
- Pending records.
- Remote versions.
- Policy and approval freshness.

`atested status` on remote shows:

- Local governance status.
- Connected or disconnected state.
- Last successful sync.
- Pending records and archives.
- Policy hash and age.
- Approval store hash and age.
- License and degraded mode state.

`atested stop`:

- Primary stops proxy, dashboard, supervisor, and sync service.
- Remote stops proxy, supervisor, and sync client.
- No chain mutation is required unless existing lifecycle events already record stop events.

## 13. Unified Report View

Layer 3 queries read:

- Primary local chain records.
- Imported JSONL sidecars whose import envelope has `verification_result=PASS`.

Default ordering:

1. `event_timestamp_utc`
2. Source machine ID
3. Local chain order within that machine

Reports must expose import metadata for remote records:

```json
{
  "machine_id": "...",
  "event_timestamp_utc": "...",
  "primary_import_timestamp_utc": "...",
  "import_envelope_hash": "sha256:..."
}
```

Machine filter modes:

- All machines.
- Primary only.
- One machine.
- Selected machines.

## 14. Evidence Export

Evidence export adds machine scope:

```text
--machines all
--machine <machine_id>
--machines <id1,id2,id3>
```

Export packages include:

- Selected records.
- Machine registry snapshot.
- Relevant import envelopes.
- Remote sidecar hashes.
- Machine attribution fields.
- Existing viewer and report format.

## 15. Telemetry

Only the primary transmits externally.

Remotes collect telemetry locally and send summaries during sync. Primary aggregates and sends one payload to Atested servers. Primary chain records telemetry transmission with payload hash and machine coverage list.

Remotes never send telemetry directly to Atested.

## 16. Communications

Primary receives Communications from Atested servers. During sync, primary relays pending messages to remotes. Remotes record local receipt and display events if existing chain event principles require them.

Messages include stable IDs so remotes can deduplicate.

## 17. Version Management

Each sync request includes remote product version and sync protocol version.

Primary tracks versions per machine. Dashboard warns on stale versions.

Primary rejects sync if:

- Sync protocol is incompatible.
- Record format is incompatible.
- Remote version is below minimum supported version.

Errors must clearly instruct the operator to update the remote.
