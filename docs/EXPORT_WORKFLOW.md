# Export Workflow

Atested provides two export paths: report exports (structured data) and
evidence packages (encrypted, self-verifying archives). Both require
authentication and both produce chain events.

## Report Export

### Authentication

1. Click the export button in any exportable view (Activity, Audit, Reports).
2. The dashboard prompts for your license key.
3. The key is validated against the licensing system.
4. On failure, a `failed_authentication_attempt` event is recorded in the chain.

### Token Creation

On successful authentication:
1. The server records a `chain_export_created` event with the authorized scope.
2. For reports specifically, a `report_exported` event records the report name,
   format, time range, and record count.
3. A signed export token is issued with a 10-minute TTL.
4. The token is bound to the authorized scope (surface, format, range).

### Scope Selection

The export scope is determined by the current view state:
- **Surface**: which view initiated the export (activity, audit, reports, approvals, configuration)
- **Format**: JSON, CSV, or Excel
- **Range**: the time window or sequence range currently selected
- **Filters**: any active filters (report ID, user, tool, decision type)
- **Chain source**: live chain or an archived chain segment
- **Machine scope**: all machines, primary only, one machine, or selected
  machines when the unified multi-machine view is used

### Download

The browser downloads the file directly. The export token is invalidated after
use. Attempting to reuse a token fails with a 403 response.

## Evidence Package Export

Evidence packages are encrypted archives for sharing with external parties.

### Flow

1. Authenticate with license key (same as report export).
2. Select the chain range to include.
3. Set a passphrase for encryption (PBKDF2-HMAC-SHA-256, 310,000 iterations).
4. The server records an `encrypted_evidence_package_created` event.
5. The package is built as a ZIP containing:
   - Encrypted chain data (AES-256-GCM)
   - A self-contained HTML viewer for decryption and verification
   - Integrity metadata (predecessor hash, operator identity)
   - Machine registry snapshot when machine scope is used
   - Relevant import envelopes and sidecar hashes for imported remote records

### Package Sources

Evidence packages can be built from:
- The live governance chain
- An archived chain segment (produced by size-based auto-archiving)
- Verified imported remote sidecars selected through the unified view

Archived chains are available as package sources because auto-archiving
preserves the full hash-linked record. An evidence package from an archive
covers the same time period the archive represents and carries the same
integrity guarantees as a live-chain package.

In multi-machine exports, the primary-local records and imported remote records
retain their original machine attribution. Remote-originated records include
`machine_id`, `event_timestamp_utc`, and `primary_import_timestamp_utc`. The
package includes the import evidence needed to tie remote records back to the
material the primary verified.

### Verification

The bundled viewer performs:
- Ciphertext hash verification
- Chain record hash-linkage verification after decryption
- Signature verification (if the chain contains signed records)

No Atested server is contacted during viewing. The math either checks out or it
does not.

## Chain Events

| Export Type | Chain Event |
|---|---|
| Any export authorization | `chain_export_created` |
| Reports surface export | `report_exported` (additionally) |
| Evidence package creation | `encrypted_evidence_package_created` |
| Failed authentication | `failed_authentication_attempt` |
