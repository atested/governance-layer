# Bypass & Regression Suite (v0.1)
Updated: 2026-02-18

## Structure
Each test has:
- TEST-ID
- Attack class
- Input (intent + tool + args)
- Expected result (ALLOW/DENY + reason code)
- Evidence expectations (record exists, log entry exists, signature valid)
- Notes

## Starter list (expand)
T-001 Unknown tool should be denied (POL-001).
T-002 Missing intent fields should be denied (POL-002).
T-003 Tool name spoofing attempt should be denied.
T-004 Parameter smuggling (nested JSON) should be denied or normalized deterministically.
T-005 Attempt tool call without broker decision record should fail hard.
T-006 Log tamper: edit prior record; verifier must flag.
T-007 Log tamper: truncate; verifier must flag.
T-008 Replay: same inputs must produce same decision.

## Filesystem write tests (Phase 1)

- T-FS-001 Disallowed base path write
  - Attack class: boundary bypass
  - Input: tool=FS_WRITE, path=/Volumes/SSD/archive/NOT_ALLOWED/out.txt
  - Expected: DENY + RC-FS-PATH-DISALLOWED
  - Evidence: decision record exists; log entry exists; signature valid

- T-FS-002 Hidden path write
  - Attack class: hidden path access
  - Input: tool=FS_WRITE, path=/Volumes/SSD/archive/gov/governance-layer/.ssh/config
  - Expected: DENY + RC-FS-HIDDEN-PATH
  - Evidence: decision record exists; log entry exists; signature valid

- T-FS-003 Path traversal attempt
  - Attack class: traversal / canonicalization
  - Input: tool=FS_WRITE, path=/Volumes/SSD/archive/gov/governance-layer/docs/../.git/config
  - Expected: DENY + RC-FS-PATH-TRAVERSAL (or RC-FS-HIDDEN-PATH if it fails earlier, but choose one and enforce deterministically)
  - Evidence: decision record exists; log entry exists; signature valid

- T-FS-004 Overwrite without explicit intent
  - Attack class: overwrite escalation
  - Input: tool=FS_WRITE, path=/Volumes/SSD/archive/gov/governance-layer/docs/SCOPE.md, overwrite flag absent
  - Expected: DENY + RC-FS-OVERWRITE-DISALLOWED
  - Evidence: decision record exists; log entry exists; signature valid

- T-FS-005 Executable output attempt
  - Attack class: executable creation
  - Input: tool=FS_WRITE, path=/Volumes/SSD/archive/gov/governance-layer/scripts/run.sh with executable permissions requested
  - Expected: DENY + RC-FS-EXECUTABLE-DISALLOWED
  - Evidence: decision record exists; log entry exists; signature valid

## Canonical request binding tests (Phase 2B)

- Script: `tests/test_canonical_request.sh`
- T-CANON-001: same semantics, different JSON bytes (FS_WRITE).
  - Expected: different `request_hash`; same normalized canonical path; deterministic DENY reason.
- T-CANON-002: same path, different `max_bytes` (FS_READ).
  - Expected: different `request_hash`; different normalized `max_bytes`; decision diverges (ALLOW vs DENY `RC-FS-MAX-BYTES-EXCEEDED`).

## FS_MOVE + POISON_MOVE tests (Phase 2C.2)

- Script: `tests/test_fs_move.sh`
- T-MOVE-001: ALLOW move within same allowed root.
  - Expected: ALLOW; normalized `canonical_src_path` and `canonical_dst_path`; replay and verify pass.
- T-MOVE-002: DENY destination path outside allowed roots.
  - Expected: DENY + `RC-FS-PATH-DISALLOWED`.
- T-MOVE-003: DENY cross-root move.
  - Expected: DENY + `RC-FS-CROSS-ROOT-DISALLOWED`.
- T-MOVE-004: DENY overwrite when `overwrite_allowed=false`.
  - Expected: DENY + `RC-FS-OVERWRITE-DISALLOWED`.
- T-POISON-MOVE-001: cap_cfg injection widening allowlist to `/`.
  - Expected: DENY + untrusted input includes `cap_cfg`.
- T-POISON-MOVE-002: argv[1] permissive registry steering.
  - Expected: DENY + untrusted input includes `cap_registry_path_arg`.

## FS_DELETE tests (Phase 2D)

- Script: `tests/test_fs_delete.sh`
- T-DELETE-001: ALLOW file within allowed root.
  - Expected: ALLOW; normalized `canonical_path` present.
- T-DELETE-002: DENY path outside allowed roots.
  - Expected: DENY + `RC-FS-PATH-DISALLOWED`.
- T-DELETE-003: DENY hidden path segment.
  - Expected: DENY + `RC-FS-HIDDEN-PATH`.
- T-DELETE-004: DENY recursive=true with recursive_allowed=false.
  - Expected: DENY + `RC-FS-RECURSIVE-DISALLOWED`.
- T-POISON-DELETE-001: cap_cfg injection widening allowlist to `/`.
  - Expected: DENY + untrusted input includes `cap_cfg`.
- T-POISON-DELETE-002: argv[1] permissive registry steering.
  - Expected: DENY + untrusted input includes `cap_registry_path_arg`.

## Attestation bundle + proof-packet / replay audit (Phase 3+)

### Attestation bundle (record + artifacts deterministic pack/verify)

- Script: `tests/test_attestation_bundle_pack.sh`
  - Locks deterministic bundle pack output bytes and manifest file map/hash generation.
- Script: `tests/test_attestation_bundle_verify.sh`
  - Locks manifest schema/hash index verification and fail-closed structure checks.
- Script: `tests/test_attestation_bundle_tamper.sh`
  - Locks tamper detection for payload/manifest mutations with stable fail markers.
- Script: `tests/test_attestation_bundle_determinism.sh`
  - Locks repeated-run byte stability and changed-input hash divergence sanity.

### Proof packet v1 (record + replay audit + artifacts)

- Script: `tests/test_proof_packet_build.sh`
  - Locks deterministic proof-packet pack bytes, manifest keys/file map, and expected members.
- Script: `tests/test_proof_packet_manifest_verify.sh`
  - Locks proof-packet manifest schema and hash-index verification behavior.
- Script: `tests/test_proof_packet_tamper_matrix.sh`
  - Locks deterministic tamper matrix coverage (payload/manifest/missing/extra/duplicate cases).
- Script: `tests/test_proof_packet_missing_components.sh`
  - Locks fail-closed handling for missing manifest/payload components and malformed manifest cases.
- Script: `tests/test_proof_packet_roundtrip_smoke.sh`
  - Locks pack→verify roundtrip, replay audit report path contract, and linkage invariants (`replay_report_hash`, `record_bytes_sha256`).
- Script: `tests/test_proof_packet_determinism.sh`
  - Locks proof-packet byte stability and canonical tar member ordering across runs.
- Script: `tests/test_proof_packet_replay_report_embed.sh`
  - Locks replay audit report embedding rules and source_summary linkage fail-closed checks.
- Script: `tests/test_proof_packet_summary_json.sh`
  - Locks deterministic verifier summary JSON keys/counts/linkage output for CI/log bundles.

Versioning/compat notes:
- Proof-packet manifest schema marker: `proof_packet_v1`
- Verifier summary JSON schema marker: `proof_packet_verify_summary_v1`
- Replay audit report linkage is validated via `source_summary.replay_report_hash` and `record_bytes_sha256` invariants in proof-packet tests.

### Replay (core + audit report)

- Script: `tests/test_replay.sh`
  - Locks replay invariants, mismatch detection, and deterministic fail-closed output for drift/tamper cases.
- Script: `tests/test_replay_audit_report.sh`
  - Locks deterministic replay audit summary JSON/report bytes and mismatch field ordering.
