# Chain Walker Specification

**Dispatch**: 148-D-2026-0427  
**Status**: Design specification, pre-implementation  
**Owner**: Atested  
**Primary surface**: Operator UI, Audit window  
**Related systems**: dashboard API, chain readout, chain verifier, integrity monitor, export authorization, external evidence viewer

## 1. Purpose

The Chain Walker is an investigation mode inside the Audit window. It lets an
operator walk the governance chain in sequence while seeing two synchronized
representations of the same records:

- a compact data row view
- a plain-language narrative view derived only from each corresponding record

The goal is to make chronological investigation usable without weakening the
chain model. The walker must preserve record order, show context around the
current record, stop on important events, support archived chains, and make
export boundaries explicit.

## 2. Current State

Relevant existing pieces:

- Audit window: `dashboard/ui-next/windows/audit.js`
- Audit APIs: `/api/audit/query`, `/api/audit/record`, `/api/audit/report`
- Chain readout helpers: `scripts/readout.py`
- Chain verification: `scripts/verify-record.py`, `scripts/atested_cli.py chain verify`, readout integrity helpers
- Integrity monitor: `scripts/integrity_monitor.py`
- Health signals: `scripts/chain_health.py`
- Export controls: Audit, Activity, Approvals, Reports, and Configuration currently expose JSON/CSV/Excel export controls after D-147

The current Audit view is table-first: filters, pagination, column visibility,
multi-format export, row detail. The Chain Walker should be added as a second
Audit mode, not a replacement for the current search/table workflow.

## 3. Product Requirements

### 3.1 Audit View Modes

The Audit window has two modes:

- `Search`: the current filter/table view.
- `Walker`: synchronized chain investigation view.

The mode switch is local to the Audit window. Switching from Search to Walker
preserves the active filters and current selection. Switching back preserves
filters and returns to the same result context where possible.

### 3.2 Walker Layout

The walker contains:

- Top pane: 11 compact chain data rows.
- Bottom pane: 11 narrative lines.
- Middle row: highlighted current record, row 6 in a 1-based count.
- Five visible records above and five visible records below the current record.

The top and bottom panes are locked together. A data row and narrative line at
the same visual position always refer to the same record.

When there are fewer than five records before or after the current position,
the walker should show blank spacer rows or edge labels rather than shifting
the current row away from the center. The highlighted record stays centered
unless the filtered result set has fewer than 11 total records.

### 3.3 Data Row Fields

Rows must use fields already present in the normalized chain record. Initial
columns:

| Field | Purpose |
|---|---|
| Sequence | Chain line or normalized sequence position |
| Time | `timestamp_utc` |
| Category | Normalized event category |
| Decision | `ALLOW`, `DENY`, or blank for non-decision events |
| Action | Governed action/tool label, if present |
| Target | Path, command, URL, artifact, or event target, if present |
| Tier | Confidence tier, if present |
| User | User/operator identity, if present |
| Hash | short `record_hash` |

Column widths must be stable. Long text truncates visually but remains available
through the tooltip and Record Detail.

### 3.4 Narrative Lines

Each narrative line is a deterministic rendering of the corresponding record.
It must not invent facts or infer intent beyond what the chain record contains.

Examples:

- `ALLOW: cecil ran FS_READ on /repo/README.md under rule allow_project_reads.`
- `DENY: cecil attempted FS_DELETE on /prod/secrets.env. Policy denied before execution.`
- `APPROVAL: operator greg approved artifact sha256:abcd... for future matching operations.`
- `REVOCATION: operator greg revoked approval sha256:abcd...; matching operations return to policy evaluation.`
- `INTEGRITY: policy rules changed from hash X to hash Y; operations are denied until acknowledged.`

Narrative generation should live in a shared readout utility, not only in UI
code, so exports and external viewers can use the same renderer.

### 3.5 Navigation

Controls:

- Step back: move one visible record backward.
- Step forward: move one visible record forward.
- Play reverse: move backward repeatedly.
- Play forward: move forward repeatedly.
- Speed selector: slow, medium, fast, extra-fast.
- Previous alert: jump to previous interesting record.
- Next alert: jump to next interesting record.
- Pause: stop playback.

Suggested playback intervals:

| Speed | Interval |
|---|---|
| Slow | 1200 ms |
| Medium | 650 ms |
| Fast | 250 ms |
| Extra-fast | 80 ms |

Playback stops automatically when the newly centered record is an alert event.
The UI should show why playback paused.

### 3.6 Alert Events

Alert events are records that deserve investigation focus. Initial definition:

- any `DENY`
- approvals
- revocations
- chain integrity violations
- policy rules changes
- proxy code hash changes
- chain file missing/truncated/count/hash mismatch events
- license state events that affect governance capability
- any record with severity `warning`, `critical`, `alert`, or equivalent

Alert detection must be implemented in one shared function so the walker,
Health links, Reports links, and external viewer agree.

### 3.7 Filtering

The walker accepts the same filters as Audit Search:

- date range
- decision
- action type
- tier
- user
- target
- event category
- action label

When filters are active, the walker walks only the matching result set. It
does not show non-matching records in between. The UI must clearly label this
as a filtered walk.

Open issue: for investigations, a filtered walk can hide causal context. The
spec recommends a `show surrounding unfiltered context` option in a later
iteration, but not in the first implementation.

### 3.8 Entry Points

The walker can open centered on:

- the first record in the filtered chain
- the currently selected Audit search row
- a Health event link
- an Alert link
- a Record Detail link
- an integrity violation break point
- a report drill-through result

If the entry record is outside the active filter result set, the UI should
offer to clear or adjust filters rather than silently failing.

## 4. Live And Archived Chains

### 4.1 Chain Sources

The walker supports:

- live chain: current `decision-chain.jsonl`
- archived chain: preserved backup from integrity violation or manual archive

The data source must be explicit in the UI:

- `Walking live chain`
- `Walking archived chain: <archive name>`

Archived chain selection should not be a simple binary toggle if multiple
archives exist. The first implementation can expose:

- View live chain
- View archived chains
- archive picker with timestamp, reason, record count, last hash

### 4.2 Archive Manifest

Each archive should have a manifest next to the archived chain file.

Required manifest fields:

| Field | Description |
|---|---|
| `archive_id` | Stable ID, timestamp plus short hash |
| `created_at_utc` | Archive creation time |
| `source_chain_path` | Original path |
| `archive_chain_path` | Archive path |
| `reason` | `integrity_violation`, `manual_archive`, etc. |
| `trigger_event_id` | Chain event or sidecar event that triggered archive |
| `record_count` | Records in archived chain |
| `first_record_hash` | First hash if present |
| `last_record_hash` | Tail hash |
| `archive_file_sha256` | Hash of archived JSONL bytes |
| `public_key_fingerprint` | Verification key fingerprint used at archive time |
| `new_chain_id` | New chain identity if a fresh chain is started |

### 4.3 Integrity Violation Preservation

The requested flow says:

1. Write one final record to the current chain documenting what was detected.
2. Preserve the current chain as a backup/archive.
3. On proxy restart, a new chain starts fresh.
4. The old chain is available in the walker.

Implementation concern:

- If the chain file is missing, unreadable, or severely truncated, writing a
  final record to that chain may be impossible or unsafe.
- If policy rules changed at runtime, writing a final record may still be
  possible.
- If chain tail verification fails, appending to the compromised chain can
  make forensic interpretation worse unless the event is explicitly marked as
  a best-effort terminal event.

Specification:

- The runtime should attempt a terminal integrity event only when the chain can
  be opened, parsed through the last trusted record, and locked safely.
- If a terminal chain event cannot be written, write an integrity sidecar event
  and archive all available bytes.
- A new chain must start with a `chain_started_after_archive` event that points
  to the archive manifest hash. This preserves continuity without pretending
  the new chain is cryptographically linked to the old one.

Tier 0 decision needed: whether a new chain after archive is acceptable as a
separate chain identity, or whether Atested must require explicit operator
acknowledgment before any fresh chain begins.

## 5. Background Verification

### 5.1 Trigger Model

Verification is usage-based, not time-based.

Default:

- verify every 100 new records
- verify immediately after any integrity event
- verify immediately before export

Configuration:

- `verification.record_interval`, default `100`
- minimum `10`
- maximum `10000`
- disabled only through an explicit debug/development flag, not normal UI

### 5.2 Runtime Behavior

The verifier must not block chain writes for long periods. Recommended shape:

1. Chain append updates a lightweight counter.
2. When threshold is crossed, queue verification.
3. Verification takes a stable snapshot path or reads under an appropriate
   shared lock.
4. Verification writes result metadata to a health sidecar.
5. Severe failures append a chain integrity event if safe.
6. Health window reads the latest verification result.

### 5.3 Result Schema

Suggested sidecar: `gov_runtime/LOGS/chain_verification_status.json`

Fields:

| Field | Description |
|---|---|
| `schema_version` | integer |
| `chain_source` | live or archive id |
| `started_at_utc` | verification start |
| `completed_at_utc` | verification end |
| `record_count_checked` | count checked |
| `first_break_sequence` | first failing sequence, if any |
| `first_break_hash` | hash at break point, if available |
| `status` | ok, warning, failed |
| `reason` | machine-readable reason |
| `summary` | short human-readable summary |

Health links to the walker centered on `first_break_sequence`.

## 6. Export Model

### 6.1 Export Levels

There are two export levels.

#### Level 1: Raw Data Export

Purpose: internal operator analysis.

Formats:

- JSON
- CSV
- Excel-compatible spreadsheet

Requirements:

- operator authentication required
- export event recorded in the chain
- files remain on operator machine
- not packaged for sharing
- not encrypted by Atested
- available from Audit Search and Walker range selection

#### Level 2: Encrypted Evidence Package

Purpose: sharing with another person.

Package contains:

- encrypted chain data
- manifest
- public verification key
- browser-based external viewer
- optional intended recipient metadata
- verification summary

Requirements:

- operator authentication required
- operator selects record range in Walker
- operator sets password
- password is never stored and never recorded in the chain
- export event recorded in the chain before or during package creation
- package can be decrypted only with the password
- package viewer verifies hashes/signatures before presenting evidence

### 6.2 Export Authorization

D-147 made exports consistent but did not add authentication gates. D-148
requires implementation to gate all export controls.

Required API shape:

- UI export button opens authentication dialog.
- Operator provides license key or operator credential.
- Dashboard server verifies credential.
- Server creates short-lived export token scoped to:
  - export level
  - chain source
  - filter/range
  - format/package operation
  - expiration time
- Export endpoint validates token before generating data.

Security note: authenticating only in browser code is not sufficient. The
server must enforce export authorization.

Tier 0 decision needed: whether license key is sufficient operator
authentication, or whether this must wait for a stronger operator identity and
role model.

### 6.3 Export Chain Events

Raw and encrypted exports must record chain events.

Suggested event types:

- `chain_export_created`
- `encrypted_evidence_package_created`

Fields:

| Field | Description |
|---|---|
| `event_type` | event type above |
| `timestamp_utc` | creation time |
| `operator_identity` | authenticated operator or license fingerprint |
| `chain_source` | live or archive id |
| `range_start_sequence` | selected start sequence |
| `range_end_sequence` | selected end sequence |
| `record_count` | count exported |
| `filters` | filters active at export time |
| `format` | json/csv/excel/package |
| `intended_recipient` | optional, never required |
| `package_manifest_hash` | encrypted package only |
| `export_file_hash` | raw export only, if practical |
| `password_recorded` | always false |

Open issue: exporting from an archived chain cannot append an event to that
archived chain if it is preserved read-only. The live chain should record the
export event and reference the archive manifest.

### 6.4 Removing Ungated Exports

Implementation must update these existing controls:

- Audit export
- Activity export
- Approvals export
- Reports export
- Configuration export

Non-operator dashboard users may view records on screen but cannot export in
any format.

Tier 0 decision needed: which dashboard users are non-operators in the current
product, since the current local dashboard does not yet expose a full user role
system.

## 7. Encrypted Evidence Package

### 7.1 Cryptography

Recommended browser-compatible baseline:

- PBKDF2-HMAC-SHA-256 through WebCrypto for password key derivation
- random 128-bit salt
- at least 310,000 iterations, configurable upward
- AES-256-GCM for encryption
- random 96-bit nonce
- manifest authenticated as additional authenticated data where practical

Argon2id would be preferable for password KDF strength, but WebCrypto does not
provide Argon2id natively. Using Argon2id requires bundling a WASM
implementation, which complicates the no-install viewer.

Tier 0 decision needed: PBKDF2-only no-dependency viewer vs Argon2id WASM for
stronger password resistance.

### 7.2 Package Layout

Suggested package directory or zip:

```
atested-evidence-package/
  manifest.json
  viewer.html
  viewer.js
  viewer.css
  public-key.json
  encrypted-chain.bin
  encrypted-chain.sha256
  verification-summary.json
```

`manifest.json` fields:

| Field | Description |
|---|---|
| `schema_version` | package schema |
| `package_id` | stable package ID |
| `created_at_utc` | creation time |
| `created_by` | operator identity/fingerprint |
| `chain_source` | live or archive id |
| `range_start_sequence` | start |
| `range_end_sequence` | end |
| `record_count` | count |
| `public_key_fingerprint` | verification key fingerprint |
| `encryption` | algorithm, kdf, salt, iterations, nonce |
| `ciphertext_sha256` | encrypted payload hash |
| `plaintext_schema` | chain record bundle schema version |
| `intended_recipient` | optional |

### 7.3 Plaintext Payload

Encrypted payload after successful decryption:

| Field | Description |
|---|---|
| `schema_version` | payload schema |
| `chain_source` | live/archive |
| `records` | selected chain records |
| `verification_summary` | verification result over selected records |
| `narratives` | deterministic narratives, or viewer may generate locally |
| `export_event_reference` | live chain event hash if available |

The payload must contain enough predecessor context to verify linkage across
the selected range. If the selected range begins in the middle of a chain, the
payload should include the prior record hash anchor and sequence position so
the recipient can verify internal continuity and understand the range boundary.

## 8. External Viewer

### 8.1 Viewer Goals

The external viewer is browser-based and requires no install. Recipient opens
the package, enters the password, and sees verified evidence.

Audience modes:

- non-technical: plain-language summaries, verified status, clear explanations
- technical: raw verification details and optional raw file download, subject
  to Tier 0 decision below

### 8.2 Verification Flow

Viewer steps:

1. Load manifest.
2. Ask for password.
3. Derive decryption key.
4. Decrypt encrypted payload.
5. Verify ciphertext hash.
6. Verify chain record hashes and selected-range linkage.
7. Verify signatures using included public key where signatures are present.
8. Render result.

Verification results:

- `Verified`: hash linkage and signatures pass for the package scope.
- `Verified with unsigned legacy records`: linkage passes; some pre-signing
  records are unsigned and labeled as legacy compatibility records.
- `Failed`: hash, signature, schema, or decrypt verification failed.

### 8.3 Non-Technical View

Must explain:

- what Atested is, one sentence
- what the governance chain is
- what verification means
- what records are included
- what the highlighted findings are
- what the viewer cannot prove

The viewer must not imply that Atested proves downstream business correctness.
It proves the governance record and its integrity within the package scope.

### 8.4 Technical View

Technical view should show:

- public key fingerprint
- package manifest
- hash and signature verification details
- record count
- selected range
- first and last record hashes
- algorithm names
- schema versions

Design contradiction:

- The requested design says technical users can download the chain file and
  public key as raw files.
- It also says there is no re-export of unencrypted data.

These cannot both be strictly true if the chain file is downloaded after
decryption. The spec offers two options:

1. Allow technical raw download inside the viewer, and document that this is an
   intentional post-decryption disclosure authorized by the password.
2. Remove raw download from the viewer and provide only encrypted package data
   plus verification details.

Tier 0 decision required before implementation.

### 8.5 Read-Only Limits

The viewer can make the UI read-only and omit export controls, but once data is
decrypted in a browser, a sufficiently technical recipient can copy it from
memory or developer tools. The product copy must not promise cryptographic
prevention of copying after decryption.

Required wording principle:

- "The viewer does not provide an unencrypted re-export function" is accurate.
- "The decrypted data cannot be copied" is not accurate.

## 9. API Additions

Proposed endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/audit/walker` | GET | Fetch 11-row window around center record |
| `/api/audit/walker/alerts/next` | GET | Find next alert in filtered source |
| `/api/audit/walker/alerts/previous` | GET | Find previous alert in filtered source |
| `/api/audit/chains` | GET | List live and archived chains |
| `/api/audit/export/auth` | POST | Verify operator and issue scoped export token |
| `/api/audit/export/raw` | POST | Generate raw export from authorized token |
| `/api/audit/export/package` | POST | Generate encrypted evidence package |

`/api/audit/walker` parameters:

- `chain_source`: live or archive id
- `center_sequence` or `record_id`
- `limit_before`: default 5
- `limit_after`: default 5
- current Audit filters

Response fields:

- `chain_source`
- `chain_label`
- `filtered`
- `center_record_id`
- `center_sequence`
- `rows`
- `narratives`
- `alerts`
- `edge_state`: beginning/end flags

## 10. Data Model Additions

Shared Python helpers should provide:

- normalize chain record for walker row
- generate narrative from normalized record
- classify alert/interesting event
- list chain sources
- load archive manifest
- verify selected range
- build export manifest

Suggested modules:

- `scripts/chain_walker.py`
- `scripts/chain_archive.py`
- `scripts/evidence_package.py`
- `scripts/export_authorization.py`

UI additions:

- Audit mode switch
- walker pane component inside `dashboard/ui-next/windows/audit.js` or split to
  `dashboard/ui-next/windows/audit-walker.js`
- export authentication dialog
- encrypted package dialog

External viewer additions:

- `dashboard/external-viewer/` or `tools/external-viewer/`
- deterministic built assets copied into package at export time

## 11. Security Requirements

- All exports require server-enforced operator authentication.
- Export auth tokens are short-lived and scoped.
- Raw export and package export write chain events.
- Password is never logged, stored, included in telemetry, included in Trouble
  reports, or written to the chain.
- Encrypted package payload is encrypted with authenticated encryption.
- Viewer verifies before rendering.
- Archived chains are read-only through the dashboard.
- Non-operator dashboard users can view but cannot export.
- Export from an archive writes the export event to the live chain, referencing
  the archive manifest.
- Export failures should not leak partial unencrypted package artifacts.

## 12. Implementation Concerns And Gaps

1. Operator identity is not fully defined.
   - The design says "operator-authenticated" and "non-operator users", but
     current local dashboard authorization is license-oriented.
   - Tier 0 must decide whether license key is enough for D-149 or whether a
     user/role model is required first.

2. Existing exports are currently ungated.
   - D-147 standardized export formats.
   - D-148 requires gating them.
   - Implementation must avoid leaving old direct client-side exports reachable.

3. Terminal event on compromised chain may be impossible.
   - Missing/truncated chain cannot always receive a final record.
   - Need best-effort terminal event plus sidecar fallback.

4. Fresh chain after violation needs explicit semantics.
   - Starting a new chain is operationally useful but creates a new chain
     identity.
   - The new chain should reference the archive manifest but cannot pretend to
     be a continuous hash chain.

5. External viewer re-export language conflicts with technical raw download.
   - Tier 0 must choose the policy.

6. Password security depends on KDF choice and password strength.
   - Browser-only PBKDF2 is simple but less resistant than Argon2id.
   - Argon2id requires WASM and increases package complexity.

7. Filtered walking can hide context.
   - First version can walk filtered results only.
   - Investigation mode will likely need optional unfiltered context around
     matches.

8. Background verification must not become a chain writer race.
   - It must follow INV-010 for any chain event appends.
   - It should prefer sidecar status writes for routine ok results.

9. Export chain event timing needs care.
   - If event is written before file generation and generation fails, event
     must show failed status or a follow-up event must correct it.
   - Recommended: create `chain_export_started`, then
     `chain_export_completed` or `chain_export_failed`, or one completed event
     after artifact hash exists.

10. Package viewer versioning needs a retention policy.
    - Old packages should remain viewable.
    - Viewer schema compatibility must be preserved or packages must embed the
      exact viewer needed.

## 13. Incremental Build Plan

### Phase 1: Readout foundation

- Add shared chain walker normalization.
- Add deterministic narrative generation.
- Add alert classification helper.
- Add tests for representative event types.
- No UI changes except optional debug CLI.

### Phase 2: Audit walker UI, live chain only

- Add Audit Search/Walker mode switch.
- Implement 11-row synchronized data/narrative panes.
- Implement step controls and center selection.
- Implement filtered walking over live chain.
- Add entry from Audit search row.
- No archive support and no encrypted export yet.

### Phase 3: Alert navigation and playback

- Add speed selector and play forward/reverse.
- Add next/previous alert jumps.
- Auto-pause on alert records.
- Add Health/Alerts links to walker break points.

### Phase 4: Background verification

- Add usage-based verifier threshold.
- Write verification sidecar.
- Feed Health window latest verification status.
- Link verification failures into walker.

### Phase 5: Archive support

- Add archive manifest model.
- List archived chains.
- Add archive picker in walker.
- Add chain source labeling.
- Add new-chain-after-archive event semantics after Tier 0 decision.

### Phase 6: Export authorization

- Add server-enforced export auth.
- Gate all current exports.
- Add export chain events.
- Update Audit, Activity, Approvals, Reports, and Configuration export flows.

### Phase 7: Encrypted evidence package

- Add package builder.
- Add password encryption.
- Add package manifest and tests.
- Add Walker range selection.
- Add package export event.

### Phase 8: External viewer

- Build no-install browser viewer.
- Add non-technical and technical modes.
- Verify package before rendering.
- Resolve raw download policy before shipping.

## 14. Tier 0 Input Required

1. Is license key verification sufficient operator authentication for export,
   or must export wait for named operator identity and roles?

2. Are non-operator dashboard users in scope for the current local dashboard,
   and how are they represented?

3. After an integrity violation, may Atested start a new chain automatically on
   restart, or must an operator explicitly acknowledge first?

4. If a chain is missing/truncated, is a sidecar-only terminal event acceptable
   when writing a final chain record is impossible?

5. Should the external viewer allow technical users to download decrypted raw
   chain records and public key, or should it omit all unencrypted export
   controls?

6. Should encrypted packages use dependency-free PBKDF2/WebCrypto or bundle
   Argon2id WASM?

7. Should raw Level 1 exports be allowed for all paid tiers, or only specific
   tiers/roles?

8. What retention and naming policy should archived chains follow?

## 15. Acceptance Criteria For Future Implementation

- Audit includes Search and Walker modes.
- Walker keeps data and narrative rows synchronized.
- Current record remains centered in the 11-row view.
- Playback and alert jumps work and pause on alert records.
- Filters apply consistently between Search and Walker.
- Live and archived chains are clearly labeled.
- Background verification updates Health and links to walker break points.
- All exports require server-side operator authentication.
- Export events are recorded in the chain.
- Encrypted packages decrypt only with password and verify before rendering.
- External viewer is read-only in UI and honest about technical copy limits.
- Existing chain verification remains compatible.
