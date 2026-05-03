# External Contracts (v1)

**Last Updated:** 2026-02-25
**Status:** Active

This document defines the stability guarantees for external consumers of the governance-layer proof-bundle outputs and schemas.

---

## Proof-Bundle Output Contract

When you run `bash system/scripts/release-gate.sh`, you receive a proof-bundle directory at:

```
out/proof-bundles/<run-id>/
```

### Required Files

The following files are **guaranteed to be present** in the proof-bundle directory:

1. **`proof_packet.tar`** - Deterministic proof-packet archive
   - Schema: `proof_packet_v1` (FROZEN within v1, see [Versioning Policy](#versioning-policy))
   - Format: USTAR tar, mtime=0, sorted members
   - Guarantee: Byte-stable for same inputs

2. **`proof_packet_verify_summary.json`** - Verifier summary
   - Schema: `proof_packet_verify_summary_v2` (ADDITIVE-ONLY within v2)
   - Compatibility: `validate-proof-bundle.sh` accepts legacy `proof_packet_verify_summary_v1` during the bounded migration window, but current `release-gate.sh` emits `proof_packet_verify_summary_v2`
   - Guarantee: Existing `v2` fields stable, new `v2` fields may be added
   - Constitutive machine-readable fields:
     - `report_version`
     - `result`
     - `packet_hash`
     - `manifest_sha256`
     - `packet_id`
     - `counts`
     - `strictness`
     - `key_linkage`
   - `key_linkage` includes stable linkage fields used by external reviewers:
     - `record_hash`
     - `record_bytes_sha256`
     - `replay_report_hash`
     - `signing_key_id`

3. **`proof_packet.sha256`** - SHA256 checksum
   - Format: `<hex-sha256>  proof_packet.tar\n` (RFC 3174 lowercase hex)

4. **`release_gate_log.txt`** - Release gate status log
   - Format: `key=value` pairs (one per line)
   - Guarantee: Existing keys stable, new keys may be added

5. **`versions.txt`** - Version metadata
   - Format: `key=value` pairs (one per line)
   - Guarantee: Existing keys stable, new keys may be added

### Optional Files

- **`queue_drift_scan.txt`**: May contain output or "INFO: queue-drift-scan unavailable\n" sentinel
  - No machine-parse guarantee (human-readable text)
- **`queue_drift_scan.json`**: Optional machine-readable queue-drift scan summary
  - Schema: `queue_drift_scan_v1` (ADDITIVE-ONLY within v1)
  - Linkage: `text_sha256` links to `queue_drift_scan.txt` bytes when both are present
  - Consistency note: this optional file is intentionally mirrored in `docs/DISTRIBUTION.md` optional outputs list.
- **`status_bundle.json`**: Optional machine-readable release-gate status summary
  - Schema: `status_bundle_v1` (ADDITIVE-ONLY within v1)
  - `strictness.value`: integer `0|1` (not string)
  - Guarantee: Existing fields remain stable; new fields may be added without renaming/removing/retyping existing fields

### External Validator Usage (`validate-proof-bundle.sh`)

Canonical CLI:
- `bash system/scripts/validate-proof-bundle.sh out/proof-bundles/<run-id>/`
- `bash system/scripts/validate-proof-bundle.sh out/proof-bundles/<run-id>/ --summary-json /tmp/validate_summary.json`
- Optional artifact co-location pattern: `--summary-json out/proof-bundles/<run-id>/validate_proof_bundle_summary.json`

Deterministic exit taxonomy:
- `0` = valid proof-bundle contract
- `1` = contract violation (required file/schema/checksum/linkage failure)
- `2` = runtime error (I/O or invocation error)

Notes:
- `--summary-json` writes deterministic compact JSON (`validate_proof_bundle_summary_v1`) with additive-only fields within v1.
- Recommended canonical filename when co-located with proof-bundle artifacts: `validate_proof_bundle_summary.json`.
- The validator checks required proof-bundle files and optional output contracts when present.
- Constitutive machine-readable fields in `validate_proof_bundle_summary_v1`:
  - `report_version`
  - `result`
  - `exit_code`
  - `bundle_dir_basename`
  - `packet_hash`
  - `summary_hash`
  - `counts`
  - `queue_drift_scan.status`
  - `queue_drift_scan_json_present`
  - `status_bundle.status`
  - `status_bundle_present`
- Conditional failure fields:
  - `contract_failures` appears on `FAIL`
  - `runtime_error` appears on `ERROR`

---

## Profile Semantics

Control proof-packet check strictness via `GOV_PROFILE` environment variable.

### dev (default)

```bash
bash system/scripts/release-gate.sh
```

- Proof-packet check: **Informational** (failure does not cause exit 1)
- Use case: Local development, testing

### ci

```bash
GOV_PROFILE=ci bash system/scripts/release-gate.sh
```

- Proof-packet check: **Gating** (failure causes exit 1)
- Use case: Continuous integration, automated validation

### Override

```bash
RELEASE_GATE_STRICT_PROOF_PACKET=0 bash system/scripts/release-gate.sh
```

Explicit `RELEASE_GATE_STRICT_PROOF_PACKET` setting overrides `GOV_PROFILE`.

**Precedence:** `RELEASE_GATE_STRICT_PROOF_PACKET` > `GOV_PROFILE` > default(dev)

---

## Versioning Policy

### Core Schemas (STRICT)

**`proof_packet_v1` manifest:**
- **FROZEN** within v1
- No field changes allowed (no add/remove/rename/change type)
- Breaking changes require v2

**`proof_packet_verify_summary_v1`:**
- **ADDITIVE-ONLY** within v1
- New fields may be added (documented in changelog)
- Existing fields cannot be removed, renamed, or changed type
- Breaking changes require v2

**`proof_packet_verify_summary_v2`:**
- **ADDITIVE-ONLY** within v2
- New fields may be added (documented in changelog)
- Existing fields cannot be removed, renamed, or changed type
- `packet_hash` shape: `{"algo":"sha256","value":"<lowercase-hex>"}`

### Auxiliary Files (STANDARD)

**`release_gate_log.txt`, `versions.txt`:**
- New keys may be added without notice
- Existing keys will not be removed without 1 release deprecation notice
- Key format changes discouraged but allowed with documentation

### Version Bump Triggers

| Change Type | Core Schema (tar, summary JSON) | Auxiliary Files (txt) |
|-------------|--------------------------------|----------------------|
| Add field/key | Document, no version bump | Document, no version bump |
| Remove field/key | **v1 → v2** (MAJOR) | Deprecate 1 release, then remove |
| Rename field/key | **v1 → v2** (MAJOR) | Deprecate old + add new |
| Change type | **v1 → v2** (MAJOR) | Avoid; treat as remove + add |

---

## Dependency Handling

### MCP Smoke Dependency (archived)

The MCP governance broker was removed in D-203. The `RELEASE_GATE_REQUIRE_MCP`
variable is no longer supported. MCP-related proof-bundle checks are skipped.

---

## Success Criteria

An external run is considered successful if:

1. `release-gate.sh` exits with code 0
2. Proof-bundle directory exists at `$PROOF_BUNDLE_OUT_BASE/$RUN_ID/`
3. All 5 required files are present

**Environment variables:**
- `PROOF_BUNDLE_OUT_BASE`: Default `<repo>/out/proof-bundles`
- `RELEASE_GATE_RUN_ID`: Auto-generated timestamp (format may change, use env var)

---

## What Is NOT Guaranteed

The following are **implementation details** and may change:

- Directory layout (`out/proof-bundles/` path may move)
- RUN_ID format (currently timestamp `YYYYMMDD_HHMMSS`, may switch to UUID/SHA)
- `queue_drift_scan.txt` format (freeform text, no parse guarantee)
- `status_bundle.json` presence (optional) and additive fields within `status_bundle_v1`
- Order of keys in `release_gate_log.txt` and `versions.txt`
- Presence of additional files beyond the 5 required

**Guidance:** Use `$PROOF_BUNDLE_OUT_BASE` and `$RELEASE_GATE_RUN_ID` env vars instead of hardcoded paths.

---

## For More Details

<!-- - **Full rationale:** See design memo (not included in public release) -->
<!-- - **Schema specs:** See ATTESTATION_SPEC.md (not included in public release) -->
<!-- - **Operational usage:** See RUNBOOK.md (not included in public release) -->
- **Quickstart:** See [README.md](README.md)

---

## Contact

For questions or issues with external contracts:
- File an issue in the governance-layer repository
- Reference this document and the relevant contract section
