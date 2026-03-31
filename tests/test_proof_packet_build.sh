#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKER="$ROOT/scripts/proof-packet.py"
FIXTURE="$ROOT/tests/fixtures/attestation_bundle/sample"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task124-proof-packet.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

OUT1="$TMPDIR_LOCAL/proof1.tar"
OUT2="$TMPDIR_LOCAL/proof2.tar"
LOG1="$TMPDIR_LOCAL/run1.log"
LOG2="$TMPDIR_LOCAL/run2.log"

python3 "$PACKER" pack \
  --record "$FIXTURE/record.json" \
  --artifacts-dir "$FIXTURE/artifacts" \
  --replay-audit-report "$FIXTURE/replay_audit_report.json" \
  --out "$OUT1" > "$LOG1"

python3 "$PACKER" pack \
  --record "$FIXTURE/record.json" \
  --artifacts-dir "$FIXTURE/artifacts" \
  --replay-audit-report "$FIXTURE/replay_audit_report.json" \
  --out "$OUT2" > "$LOG2"

grep -q '^PROOF_PACKET_PACK ok=yes reason=OK ' "$LOG1"
grep -q ' proof_packet_version=proof_packet_v1 ' "$LOG1"
grep -q ' packet_id=ppb_' "$LOG1"
grep -q ' manifest_sha256=sha256:' "$LOG1"
grep -q ' packet_sha256=sha256:' "$LOG1"
grep -q ' replay_report_hash=sha256:' "$LOG1"
grep -q ' record_bytes_sha256=sha256:' "$LOG1"
echo "PASS: proof-packet pack emits machine-readable handoff line"

SHA1="$(python3 - <<'PY' "$OUT1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
)"
SHA2="$(python3 - <<'PY' "$OUT2"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
)"
[[ "$SHA1" == "$SHA2" ]]
echo "PROOF_PACKET_SHA256_RUN1=$SHA1"
echo "PROOF_PACKET_SHA256_RUN2=$SHA2"
echo "PASS: proof-packet bytes deterministic across two runs"

python3 - <<'PY' "$OUT1"
import json, sys, tarfile
p = sys.argv[1]
with tarfile.open(p, 'r:') as tf:
    names = tf.getnames()
    assert names == sorted(names), f"archive member order not sorted: {names}"
    expected = [
        "manifest.json",
        "payload/artifacts/request.txt",
        "payload/artifacts/response.txt",
        "payload/record.json",
        "payload/replay_audit_report.json",
    ]
    assert names == expected, names
    m = json.load(tf.extractfile("manifest.json"))
    assert sorted(m.keys()) == ["files", "hash_algo", "proof_packet_version", "source_summary"], sorted(m.keys())
    assert m["proof_packet_version"] == "proof_packet_v1"
    assert m["hash_algo"] == "sha256"
    files = m["files"]
    assert sorted(files.keys()) == [
        "artifacts/request.txt",
        "artifacts/response.txt",
        "record.json",
        "replay_audit_report.json",
    ], sorted(files.keys())
    for rel, meta in files.items():
        assert set(meta.keys()) == {"sha256", "size_bytes"}, (rel, meta)
        assert isinstance(meta["size_bytes"], int) and meta["size_bytes"] >= 0
        assert isinstance(meta["sha256"], str) and meta["sha256"].startswith("sha256:")
    src = m["source_summary"]
    assert src["record_hash"].startswith("sha256:")
    assert src["replay_report_hash"].startswith("sha256:")
print("PASS: proof-packet contains expected members and manifest required keys/file map")
PY
