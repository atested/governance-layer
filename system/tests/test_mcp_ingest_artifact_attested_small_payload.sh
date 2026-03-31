#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_ingest_artifact_attested_small_payload"
SUMDIR="out/test_mcp_ingest_artifact_attested_small_payload_out"
rm -rf "$TMP_ROOT" "$SUMDIR" out/mcp_exec out/mcp_attestation out/mcp_ingest
mkdir -p "$TMP_ROOT" "$SUMDIR"

PRIVATE_PEM='-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIPFVBLmFaiKlEPwC2vjcA6z2OTsG0euiU2Gq4CzhG+7D
-----END PRIVATE KEY-----
'

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" out/mcp_exec out/mcp_attestation out/mcp_ingest
  mkdir -p "$TMP_ROOT"

  python3 - "$ROOT" "$PRIVATE_PEM" "$out_file" <<'PY'
import base64
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
private_pem = sys.argv[2]
out_file = pathlib.Path(sys.argv[3])

payload = base64.b64encode(b"ingest-small-payload-v0").decode("ascii")
req = {
    "id": "INGEST_SMALL",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "INGEST_ARTIFACT",
            "params": {
                "payload_b64": payload,
                "provenance": {
                    "source_identifier": "TEST_SRC",
                    "extraction_date": "2026-03-06",
                },
            },
        },
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": "RID_INGEST_SMALL",
            "attested": True,
            "signing_key": private_pem,
            "attestation_out_dir": "out/test_mcp_ingest_artifact_attested_small_payload/attestation/RID_INGEST_SMALL",
        },
    },
}
proc = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if proc.returncode != 0:
    raise SystemExit("FAIL:RPC_RC")
resp = json.loads(proc.stdout.strip())["result"]

if resp.get("executed") is not True:
    raise SystemExit("FAIL:NOT_EXECUTED")
if resp.get("reason_token") != "OK":
    raise SystemExit("FAIL:REASON")
if resp.get("signature", {}).get("valid") is not True:
    raise SystemExit("FAIL:SIG_INVALID")
if resp.get("attestation_bundle", {}).get("verified") is not True:
    raise SystemExit("FAIL:BUNDLE_NOT_VERIFIED")
if resp.get("receipt_ref") != "out/mcp_ingest/RID_INGEST_SMALL/action_record.json":
    raise SystemExit("FAIL:RECEIPT_REF")

artifact = root / "out/mcp_ingest/RID_INGEST_SMALL/artifact.bin"
ingest_record = root / "out/mcp_ingest/RID_INGEST_SMALL/action_record.json"
if not artifact.is_file() or not ingest_record.is_file():
    raise SystemExit("FAIL:INGEST_ARTIFACTS_MISSING")

bundle_dir = root / "out/test_mcp_ingest_artifact_attested_small_payload/attestation/RID_INGEST_SMALL"
vproc = subprocess.run(
    ["python3", str(root / "scripts/verify-attestation-bundle.py"), str(bundle_dir)],
    text=True,
    capture_output=True,
    check=False,
)
if vproc.returncode != 0:
    raise SystemExit("FAIL:BUNDLE_VERIFY")

summary = {
    "executed": resp.get("executed"),
    "reason_token": resp.get("reason_token"),
    "receipt_ref": resp.get("receipt_ref"),
    "bundle_ref": resp.get("bundle_ref"),
    "signature_valid": resp.get("signature", {}).get("valid"),
    "bundle_verified": resp.get("attestation_bundle", {}).get("verified"),
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$SUMDIR/run1.json"
R2="$SUMDIR/run2.json"
run_once "$R1"
run_once "$R2"

H1="$(shasum -a 256 "$R1" | awk '{print $1}')"
H2="$(shasum -a 256 "$R2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_INGEST_ARTIFACT_ATTESTED_SMALL_PAYLOAD=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
