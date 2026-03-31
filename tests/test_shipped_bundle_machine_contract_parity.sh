#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/bundle-machine-contract-parity.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

scan_once() {
  local out="$1"
  python3 - <<'PY' "$ROOT" > "$out"
import pathlib, re, sys

root = pathlib.Path(sys.argv[1])
contracts = (root / "docs/EXTERNAL_CONTRACTS.md").read_text(encoding="utf-8")
distribution = (root / "docs/DISTRIBUTION.md").read_text(encoding="utf-8")
proof_packet = (root / "scripts/proof-packet.py").read_text(encoding="utf-8")
validate_summary_test = (root / "tests/test_validate_proof_bundle_summary_json_contract.sh").read_text(encoding="utf-8")
proof_packet_summary_test = (root / "tests/test_proof_packet_summary_json.sh").read_text(encoding="utf-8")

print("--- T-SHIPPED-BUNDLE-CONTRACT-PARITY-001: external docs match machine-readable bundle summary contracts ---")

required_doc_tokens = [
    "proof_packet_verify_summary_v1",
    "validate_proof_bundle_summary_v1",
    "validate_proof_bundle_summary.json",
    "packet_hash",
    "manifest_sha256",
    "packet_id",
    "summary_hash",
    "queue_drift_scan_json_present",
    "status_bundle_present",
]
for token in required_doc_tokens:
    if token not in contracts and token not in distribution:
        print(f"FAIL: docs missing contract token {token}")
        raise SystemExit(1)
    print(f"PASS: docs mention {token}")

for token in ("manifest_sha256", "packet_id", "packet_hash", "key_linkage"):
    if token not in proof_packet:
        print(f"FAIL: proof-packet implementation missing token {token}")
        raise SystemExit(1)
    print(f"PASS: proof-packet implementation exposes {token}")

validator_test_tokens = [
    "validate_proof_bundle_summary_v1",
    "queue_drift_scan_json_present",
    "status_bundle_present",
    "packet_hash",
    "summary_hash",
]
for token in validator_test_tokens:
    if token not in validate_summary_test:
        print(f"FAIL: validator summary contract test missing token {token}")
        raise SystemExit(1)
    print(f"PASS: validator summary contract test asserts {token}")

packet_test_tokens = [
    "proof_packet_verify_summary_v1",
    "packet_hash",
    "manifest_sha256",
    "packet_id",
    "key_linkage",
]
for token in packet_test_tokens:
    if token not in proof_packet_summary_test:
        print(f"FAIL: proof-packet summary contract test missing token {token}")
        raise SystemExit(1)
    print(f"PASS: proof-packet summary contract test asserts {token}")

print("PASS: shipped-bundle machine-readable contract docs and parity evidence aligned")
PY
}

run1="$TMPDIR_LOCAL/run1.out"
run2="$TMPDIR_LOCAL/run2.out"
scan_once "$run1"
scan_once "$run2"
cat "$run1"
D1="$(sha256_file "$run1")"
D2="$(sha256_file "$run2")"
echo "SHIPPED_BUNDLE_CONTRACT_PARITY_SHA256_RUN1=$D1"
echo "SHIPPED_BUNDLE_CONTRACT_PARITY_SHA256_RUN2=$D2"
[[ "$D1" == "$D2" ]] || { echo "FAIL: parity output nondeterministic"; exit 1; }
echo "PASS: shipped-bundle machine contract parity deterministic across two runs"
