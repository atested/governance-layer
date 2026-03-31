# Distribution Manifest (External Use)

## Purpose
This document lists the minimum files and outputs needed to distribute and validate the project for external use without relying on local development state.

## Required Repository Files (Ship)
- `README.md` (quickstart + output interpretation)
- `docs/EXTERNAL_CONTRACTS.md` (proof-bundle external contract)
- `docs/TEST-SUITE.md` (test catalogue)
- `docs/dev/ATTESTATION_SPEC.md` (attestation/proof-packet linkage reference)
- `system/scripts/bootstrap-run.sh` (one-command setup / runner)
- `system/scripts/release-gate.sh` (proof-bundle emitter)
- `system/scripts/validate-proof-bundle.sh` (external contract validator)

## Expected Runtime Outputs (Generated, Not Committed)
Required proof-bundle files (external contract minimum):
- `out/proof-bundles/<run-id>/proof_packet.tar`
- `out/proof-bundles/<run-id>/proof_packet.sha256`
- `out/proof-bundles/<run-id>/proof_packet_verify_summary.json`
- `out/proof-bundles/<run-id>/release_gate_log.txt`
- `out/proof-bundles/<run-id>/versions.txt`
Optional additive files:
- Optional: `out/proof-bundles/<run-id>/queue_drift_scan.txt`
- Optional: `out/proof-bundles/<run-id>/queue_drift_scan.json`
- Optional: `out/proof-bundles/<run-id>/status_bundle.json`
- Optional: `out/proof-bundles/<run-id>/validate_proof_bundle_summary.json`

## Do Not Commit (Runtime / Local-Only)
- `out/proof-bundles/**` (runtime outputs)
- `.venv/`
- `__pycache__/`
- editor swap files / local artifacts (e.g., `*.swp`, `.DS_Store`)

## Canonical Validation Commands
- `bash system/scripts/bootstrap-run.sh --dry-run`
- `GOV_PROFILE=ci bash system/scripts/release-gate.sh`
- `bash system/scripts/validate-proof-bundle.sh out/proof-bundles/<run-id>/`
- Optional summary JSON: `bash system/scripts/validate-proof-bundle.sh out/proof-bundles/<run-id>/ --summary-json /tmp/validate_summary.json`

## External Packaging Smoke Contract
- Smoke check script: `bash tests/test_external_packaging_smoke.sh`
- Deterministic runner markers used by the bounded suite:
  - `BEGIN:TASK165`, `BEGIN:TASK168`, `BEGIN:TASK169`, `BEGIN:TASK171`, `BEGIN:TASK172`
  - matching `END:<task> rc=<n>` lines
- Required docs anchors for smoke scans:
  - required outputs: `proof_packet.tar`, `proof_packet_verify_summary.json`, `proof_packet.sha256`, `release_gate_log.txt`, `versions.txt`
  - optional outputs: `queue_drift_scan.txt`, `queue_drift_scan.json`, `status_bundle.json`
