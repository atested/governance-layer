# Multi-Machine Governance Implementation Plan v1

Status: Ready for build planning
Date: 2026-05-06
Spec: `docs/specs/multi-machine-governance-spec-v1.md`

## Implementation Strategy

Build in six batches. The ordering keeps single-machine behavior stable while adding multi-machine capability in layers:

1. Machine identity and record freshness fields.
2. Machine registry and authorization state.
3. Import envelopes and remote record storage.
4. Sync transport and primary-to-remote state distribution.
5. Operator lifecycle, removal, restore, and degraded mode.
6. Layer 3 reporting, evidence export, telemetry, Communications, and version management.

Each batch should include focused unit tests and one integration path. Do not start transport work until local import verification and idempotent storage are deterministic.

## Batch 1: Machine Identity And Record Fields

Goal: every local record is machine-attributed and binds the policy and approval versions used for the decision.

Tasks:

- Add first-run machine identity creation in `gov_runtime`.
- Persist machine config:
  - `installation_id`
  - `machine_id`
  - `machine_role`
  - display name
  - primary address if remote
  - machine signing key fingerprint
- Add `machine_id`, `machine_role`, and `event_timestamp_utc` to all new governance records.
- Add `approval_store_hash` to decision records.
- Ensure `policy_rules_hash` is present and consistently computed in decision records.
- Update canonical hashing paths so new fields are included intentionally.
- Keep `timestamp_utc` compatibility if existing code expects it.

Tests:

- First-run identity is stable after restart.
- Local records include machine fields.
- Decision records include `approval_store_hash` and `policy_rules_hash`.
- Record hash verification passes with the new fields.
- Existing single-machine flows still pass.

Exit criteria:

- A single-machine install behaves as before, with additional machine metadata in records.

## Batch 2: Machine Registry And Authorization State

Goal: the primary has an auditable registry of machines and authorization decisions.

Tasks:

- Implement primary registry file:

```text
gov_runtime/machines/registry.json
```

- Add canonical `registry_hash` computed with `registry_hash=null`.
- Support historical keys per machine with validity windows.
- Implement authorized machine lookup:
  - machine exists
  - active license status
  - `sync_authorized=true`
  - key fingerprint matches an active key window
  - local operator confirmation was recorded
- Add registry chain events:
  - `machine_added`
  - `machine_removed`
  - `machine_role_changed`
  - `machine_key_rotated`
  - `machine_license_status_changed`
- Add helper APIs for adding, removing, updating license status, and rotating keys.

Tests:

- Registry hash is deterministic.
- Authorized lookup accepts only active registered machines.
- Removed or revoked machines cannot sync.
- Registry events are appended and hash-verified.
- Historical key windows verify records signed during the correct interval.

Exit criteria:

- A primary can maintain an auditable registry before any sync transport exists.

## Batch 3: Import Envelopes And Remote Record Storage

Goal: the primary can verify and import remote material locally without a network protocol.

Tasks:

- Implement import envelope builder for `remote_chain_import`.
- Implement stable `segment_id`.
- Add JSONL sidecar storage:

```text
gov_runtime/imports/<source_machine_id>/<segment_id>.jsonl
gov_runtime/imports/<source_machine_id>/<segment_id>.manifest.json
```

- Bind sidecar content through `stored_segment_sha256`.
- Implement idempotent import:
  - same segment ID and same bytes returns existing import envelope hash
  - same segment ID with different bytes rejects
- Verify remote segment material:
  - parseable JSONL
  - record hashes
  - signatures
  - machine ID consistency
  - key validity
  - chain linkage
  - continuity from previous imported remote tail
- Verify archive manifests and archive continuity.
- Append `remote_chain_import` envelope to the primary chain after successful verification.
- Ensure failed imports do not enter the Layer 3 query set.

Tests:

- Valid remote segment imports and creates sidecar plus envelope.
- Broken linkage rejects.
- Wrong machine ID rejects.
- Bad signature rejects.
- Duplicate retry is idempotent.
- Same segment ID with different bytes rejects.
- Archive continuity failure rejects.
- Sidecar tamper is detected by envelope-bound hash.

Exit criteria:

- Import can be exercised from local fixtures without a running sync service.

## Batch 4: Sync Transport And State Distribution

Goal: remotes can send verified signed segments to the primary over v1 HTTP sync and receive current shared state.

Tasks:

- Add primary HTTP sync endpoints:
  - `POST /sync/v1/session/start`
  - `POST /sync/v1/segment`
  - optional `POST /sync/v1/session/finish`
- Add remote sync client.
- Implement session nonce handling.
- Sign requests with method, path, session ID, request number, timestamp, body hash, and nonce-derived binding.
- Sign primary responses and verify them on the remote.
- Reject stale session IDs, reused nonces, repeated request numbers, and segment body hash conflicts.
- Add retry and failure backoff:

```text
30s -> 2m -> 5m -> baseline interval
```

- Track pending local segments and mark them synced only after receipt confirmation.
- Return primary-to-remote state bundle:
  - approval store and hash
  - policy snapshot and hash
  - Communications
  - version info
  - machine registry hash and replicated restore metadata
- Store received approval and policy snapshots on remotes.
- Ensure remote decisions bind the received approval and policy hashes.

Tests:

- Handshake succeeds for authorized remote.
- Unknown machine rejects.
- Removed machine rejects.
- Stale nonce/session rejects.
- Request number replay rejects.
- Response signature verification catches tamper.
- Remote retry does not duplicate imports.
- Remote receives and uses approval/policy hashes.

Exit criteria:

- Two local test runtimes can sync over HTTP with app-level signatures.

## Batch 5: Operator Lifecycle, Removal, Restore, And Degraded Mode

Goal: the feature is operable through CLI and resilient to common lifecycle events.

Tasks:

- Update `atested start` primary bootstrap:
  - create runtime
  - generate machine ID and signing key
  - set role `primary`
  - create registry
  - start proxy, dashboard, supervisor, and sync service
- Update `atested start` remote join:
  - create runtime
  - generate machine ID and signing key
  - prompt for primary address
  - present license authorization and public key
  - require primary-side local operator confirmation before registry add
  - start proxy and supervisor with sync enabled
- Add or extend `atested sync`.
- Update `atested status` on primary:
  - primary health
  - sync service status
  - machine list
  - last sync per remote
  - pending records
  - remote versions
  - policy and approval freshness
- Update `atested status` on remote:
  - local governance status
  - connected or disconnected state
  - last successful sync
  - pending records and archives
  - policy hash and age
  - approval store hash and age
  - license and degraded mode state
- Update `atested stop`:
  - primary stops proxy, dashboard, supervisor, and sync service
  - remote stops proxy, supervisor, and sync client
- Implement machine removal:
  - set `license_status=removed`
  - set `sync_authorized=false`
  - append `machine_removed`
  - preserve historical sidecars and envelopes
- Implement remote degraded or unlicensed mode after removal:
  - stop syncing
  - continue local governance if allowed
  - mark status and records clearly
- Document and validate primary restore from backup.

Tests:

- Primary first start creates expected runtime state.
- Remote join requires primary confirmation.
- Status reflects pending sync and freshness.
- Removed remote cannot sync and enters degraded mode.
- Historical imports remain visible after removal.
- Restored primary verifies runtime and accepts existing remotes if key material is restored.

Exit criteria:

- Operator can run primary and remote lifecycle commands without manual file edits.

## Batch 6: Layer 3 Queries, Export, Telemetry, Communications, And Versions

Goal: multi-machine data is visible and exportable while preserving source integrity.

Tasks:

- Build derived import index from sidecars and envelopes.
- Merge primary-local records and verified imported remote records.
- Add machine filter modes:
  - all machines
  - primary only
  - one machine
  - selected machines
- Display both:
  - `event_timestamp_utc`
  - `primary_import_timestamp_utc`
- Add machine filters to reports, Activity, Audit, Walker, and evidence export.
- Evidence exports include:
  - selected records
  - machine registry snapshot
  - relevant import envelopes
  - sidecar hashes
  - machine attribution fields
  - existing viewer and report format
- Add telemetry aggregation:
  - remotes send local summaries during sync
  - primary aggregates
  - only primary transmits externally
  - primary chain records payload hash and machine coverage
- Add Communications relay:
  - primary receives server messages
  - primary relays during sync
  - remotes deduplicate by stable message ID
- Add version management:
  - sync requests include product version and protocol version
  - primary tracks versions per machine
  - dashboard/status warn on stale versions
  - incompatible remotes are rejected with update-required errors
- Implement product-update policy refresh semantics:
  - primary records new `policy_rules_hash`
  - remotes receive updated policy on next sync
  - connected remotes may be prompted to sync quickly
  - this is not treated as an operator policy-edit trigger

Tests:

- Unified query merges primary and remote records.
- Machine filters produce correct subsets.
- Remote records show event time and import time.
- Evidence export validates for all machines, one machine, and selected machines.
- Remote telemetry is never sent externally by the remote.
- Communications relay deduplicates messages.
- Version mismatch rejects sync with a clear update-required error.

Exit criteria:

- Multi-machine records are queryable, reportable, exportable, and auditable end to end.

## Cross-Batch Requirements

- Preserve single-machine behavior throughout.
- Keep remote records immutable after import.
- Keep SQLite indexes rebuildable from integrity-bound material.
- Ensure app-level signatures are mandatory for sync even over HTTP.
- Keep confidentiality out of v1 sync guarantees unless encrypted transport is explicitly added.
- Add migration paths for existing single-machine runtimes.
- Keep full remote promotion out of v1; support restore from backup.

## Suggested Validation Gates

After Batch 1:

```text
single-machine chain append and verify passes with machine fields
```

After Batch 3:

```text
offline remote fixture import creates sidecar and envelope; tamper is detected
```

After Batch 4:

```text
two local runtimes sync over HTTP with signed requests and idempotent segment import
```

After Batch 6:

```text
evidence export for selected machines verifies and includes required import evidence
```
