# Chain Walker Implementation Plan

**Dispatch**: 149-D-2026-0427  
**Status**: Review plan, not implementation authorization  
**Spec**: `docs/specs/chain-walker-spec.md`  
**Primary surface**: Audit window and dashboard API

## Purpose

This plan translates the Chain Walker specification into an incremental build
sequence. Each phase should be separately reviewable and testable. Later phases
depend on the shared readout, chain source, and export authorization foundations
from earlier phases.

## Phase 1: Readout Foundation

What gets built:

- Shared chain record normalization for walker rows.
- Deterministic narrative generation from normalized records.
- Shared alert classification helper.
- Filter application helper that matches Audit Search behavior.
- Unit tests for mediated decisions, approvals, revocations, integrity events,
  license events, legacy unsigned records, and malformed records.

Likely affected files:

- `scripts/readout.py`
- `scripts/chain_walker.py` (new)
- `scripts/event_model.py`
- `tests/` or existing shell/Python test locations
- `dashboard/server.py` only if a debug endpoint is useful for early testing

Dependencies:

- Existing chain readout and audit query behavior.
- Existing event model and D-139 integrity event types.

Complexity: medium

Remaining open questions:

- Whether to keep walker helpers inside `readout.py` or split immediately into
  `scripts/chain_walker.py`.
- Exact narrative wording for all historical non-action event types.

## Phase 2: Audit Walker UI, Live Chain Only

What gets built:

- Audit Search/Walker mode switch.
- Live-chain-only walker pane.
- 11-row synchronized data and narrative view.
- Center record selection and step forward/back.
- Filtered walking over live chain using existing Audit filters.
- Entry from Audit search result row into Walker centered on that record.

Likely affected files:

- `dashboard/ui-next/windows/audit.js`
- `dashboard/ui-next/windows/audit-walker.js` (new, preferred)
- `dashboard/ui-next/api.js`
- `dashboard/server.py`
- `scripts/chain_walker.py`
- demo propagation files after product implementation

Dependencies:

- Phase 1 normalization, narrative, alert, and filtering helpers.

Complexity: large

Remaining open questions:

- Whether the walker UI should live in `audit.js` or a new `audit-walker.js`
  imported by Audit.
- Exact compact row columns after reviewing real chain variety.
- Whether first implementation should virtualize large filtered result sets or
  rely on server windowing only.

## Phase 3: Playback And Alert Navigation

What gets built:

- Play forward and play reverse.
- Speed selector: slow, medium, fast, extra-fast.
- Pause control.
- Jump to next alert and previous alert.
- Auto-pause on alert records.
- Small status text explaining why playback paused.

Likely affected files:

- `dashboard/ui-next/windows/audit-walker.js`
- `dashboard/ui-next/windows/audit.js`
- `dashboard/ui-next/api.js`
- `dashboard/server.py`
- `scripts/chain_walker.py`

Dependencies:

- Phase 2 walker UI.
- Phase 1 alert classification helper.

Complexity: medium

Remaining open questions:

- Whether alert jumps should search within the current filtered set only or
  optionally ignore filters. Spec v1 says filtered set only.
- Whether playback state should persist when switching back to Search mode.

## Phase 4: Background Verification

What gets built:

- Usage-based verification threshold, default every 100 new records.
- Verification queue/runner that does not block normal chain appends.
- Verification status sidecar:
  `gov_runtime/LOGS/chain_verification_status.json`.
- Health window reads latest verification status.
- Health failure links open Audit Walker centered on first break point.
- Verification runs immediately before export.

Likely affected files:

- `scripts/chain_health.py`
- `scripts/integrity_monitor.py`
- `scripts/chain_walker.py`
- `dashboard/server.py`
- `dashboard/ui-next/windows/health.js`
- `dashboard/ui-next/windows/audit-walker.js`
- possibly `proxy/server.py` if append counters live in the proxy path

Dependencies:

- Phase 1 chain range verification helpers.
- Phase 2 walker entry by sequence or record id.

Complexity: large

Remaining open questions:

- Best process model for background verification in the current lightweight
  dashboard/proxy architecture.
- Whether verification trigger state belongs in integrity metadata or a
  separate sidecar.
- How to avoid duplicate verification jobs when dashboard and proxy are both
  active.

## Phase 5: Archive Support

What gets built:

- Archive manifest model.
- Archive listing API.
- Archive picker in Walker.
- Clear live/archive labeling.
- Read-only archived chain loading.
- Automatic fresh chain start after integrity archive on proxy restart.
- `chain_started_after_archive` event in the fresh chain.
- Sidecar-only terminal evidence fallback when final chain append is impossible.

Likely affected files:

- `scripts/chain_archive.py` (new)
- `scripts/integrity_monitor.py`
- `scripts/chain_health.py`
- `proxy/server.py`
- `dashboard/server.py`
- `dashboard/ui-next/windows/audit-walker.js`
- `scripts/event_model.py`
- tests for missing/truncated/tail-mismatch archive behavior

Dependencies:

- Phase 1 chain source abstraction.
- Phase 2 walker can accept `chain_source`.
- D-139 integrity metadata behavior.

Complexity: large

Remaining open questions:

- Exact archive directory naming convention.
- Whether manual archive creation belongs in this phase or a later admin tool.
- How much archive manifest detail should be shown in Health versus Walker.

## Phase 6: Export Authorization And Existing Export Gates

What gets built:

- Server-enforced export authentication using valid license key.
- Short-lived scoped export token.
- Export-auth dialog in UI.
- Gate existing exports:
  - Audit
  - Activity
  - Approvals
  - Reports
  - Configuration
- Raw Level 1 exports available to any operator with a license key and no tier
  restriction.
- Export events recorded in the live chain.
- Export from archived chain records a live-chain event referencing archive
  manifest.

Likely affected files:

- `dashboard/server.py`
- `dashboard/ui-next/export-utils.js`
- `dashboard/ui-next/windows/audit.js`
- `dashboard/ui-next/windows/activity.js`
- `dashboard/ui-next/windows/approvals.js`
- `dashboard/ui-next/windows/reports.js`
- `dashboard/ui-next/windows/configuration.js`
- `dashboard/ui-next/api.js`
- `scripts/event_model.py`
- `scripts/atested_cli.py` if CLI exports are added or gated
- demo API/window files after propagation

Dependencies:

- Existing license validation path.
- Phase 1 export event schema decisions.
- Phase 4 pre-export verification if enforcement is included immediately.

Complexity: large

Remaining open questions:

- Token storage: in-memory only versus signed short-lived token.
- Whether export auth should be per export click or reusable for a short
  session window.
- Whether Configuration export should remain in the same gate as chain exports
  or use a lighter configuration-specific gate.

## Phase 7: Encrypted Evidence Package

What gets built:

- Walker range selection.
- Encrypted package creation API.
- Package manifest.
- PBKDF2-HMAC-SHA-256 key derivation through WebCrypto-compatible parameters.
- AES-256-GCM encryption.
- Password validation: minimum 12 characters only.
- Package chain event.
- Tests for package manifest, encryption metadata, decrypt failure, and selected
  range verification.

Likely affected files:

- `scripts/evidence_package.py` (new)
- `scripts/chain_walker.py`
- `scripts/export_authorization.py` (new)
- `dashboard/server.py`
- `dashboard/ui-next/windows/audit-walker.js`
- `dashboard/ui-next/api.js`
- `scripts/event_model.py`
- tests

Dependencies:

- Phase 1 normalization and selected range verification.
- Phase 2 or Phase 3 walker range selection.
- Phase 6 export authorization.

Complexity: large

Remaining open questions:

- Whether encryption happens server-side in Python or client-side in browser.
  Server-side is easier to package; client-side reduces password exposure to
  server code but complicates file assembly.
- Exact package file format: directory, zip, or single HTML bundle plus
  ciphertext.

## Phase 8: External Viewer

What gets built:

- Browser-based no-install viewer.
- Password prompt and WebCrypto decrypt path.
- Verification before rendering.
- Non-technical view with plain-language summaries.
- Technical view with manifest, public key fingerprint, hash/signature status,
  algorithms, schema versions, and selected range metadata.
- View-only UI with no raw decrypted download controls.
- Compatibility tests using generated package fixtures.

Likely affected files:

- `dashboard/external-viewer/` or `tools/external-viewer/` (new)
- `scripts/evidence_package.py`
- `dashboard/server.py` package assembly path
- docs for viewer use
- website docs later, if/when product direction asks for public-facing docs

Dependencies:

- Phase 7 package format and crypto metadata.
- Phase 1 narrative generation or a viewer-portable narrative renderer.

Complexity: large

Remaining open questions:

- Whether the viewer is embedded as static files copied into each package or
  bundled into a single self-contained `viewer.html`.
- How much CSS/design polish is needed before customer-facing use.
- Browser support floor for WebCrypto and local file loading.

## Cross-Phase Testing Strategy

- Unit tests for normalization, narratives, alert classification, archive
  manifests, and export event construction.
- Integration tests for `/api/audit/walker`, chain source switching, and
  next/previous alert queries.
- Regression tests for existing Audit Search filters and exports.
- Integrity tests for missing chain, truncated chain, tail mismatch, and
  sidecar-only fallback.
- Encryption tests for PBKDF2/AES-GCM metadata and wrong-password failure.
- External viewer fixture tests for verified, legacy unsigned, and failed
  package states.

## Recommended Review Order

1. Review Phase 1 data model and narrative wording first.
2. Review Phase 6 export authorization before any encrypted package work.
3. Review Phase 5 archive semantics with D-139 integrity behavior before
   changing proxy restart behavior.
4. Review Phase 8 viewer copy before customer-facing use.
