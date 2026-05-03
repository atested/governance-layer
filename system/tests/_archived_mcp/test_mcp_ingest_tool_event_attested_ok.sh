#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_ingest_tool_event_attested_ok"
SUMDIR="out/test_mcp_ingest_tool_event_attested_ok_out"
rm -rf "$TMP_ROOT" "$SUMDIR" out/mcp_exec out/mcp_attestation out/mcp_ingest_tool_event
mkdir -p "$TMP_ROOT" "$SUMDIR"

PRIVATE_PEM="$(cat "$ROOT/system/tests/fixtures/keys/ed25519_test_private.pem")"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" out/mcp_exec out/mcp_attestation out/mcp_ingest_tool_event
  mkdir -p "$TMP_ROOT"

  python3 - "$ROOT" "$PRIVATE_PEM" "$out_file" <<'PY'
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
private_pem = sys.argv[2]
out_file = pathlib.Path(sys.argv[3])

p_digest = "sha256:" + hashlib.sha256(b"params-v0").hexdigest()
out1 = "sha256:" + hashlib.sha256(b"output-1").hexdigest()
out2 = "sha256:" + hashlib.sha256(b"output-2").hexdigest()

req = {
    "id": "INGEST_TOOL_EVENT_OK",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "INGEST_TOOL_EVENT",
            "params": {
                "tool_event_version": "v0",
                "tool_name": "TEST_TOOL",
                "tool_params_digest": p_digest,
                "exit_code": 0,
                "outputs": [
                    {"name": "stdout", "digest": out1, "ref_type": "blob"},
                    {"name": "artifact", "digest": out2, "ref_type": "file"},
                ],
                "provenance": {
                    "source_identifier": "TEST_SRC",
                    "extraction_date": "2026-03-06",
                },
                "policy_context_used": "DEFAULT",
            },
        },
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": "RID_TOOL_EVENT_OK",
            "attested": True,
            "signing_key": private_pem,
            "attestation_out_dir": "out/test_mcp_ingest_tool_event_attested_ok/attestation/RID_TOOL_EVENT_OK",
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

te_path = root / "out/mcp_ingest_tool_event/RID_TOOL_EVENT_OK/tool_event.v0.json"
if not te_path.is_file():
    raise SystemExit("FAIL:TOOL_EVENT_FILE_MISSING")
te = json.loads(te_path.read_text(encoding="utf-8"))
if te.get("tool_name") != "TEST_TOOL":
    raise SystemExit("FAIL:TOOL_NAME")

bundle_dir = root / "out/test_mcp_ingest_tool_event_attested_ok/attestation/RID_TOOL_EVENT_OK"
if not (bundle_dir / "payload/artifacts/tool_event.v0.json").is_file():
    raise SystemExit("FAIL:BUNDLE_TOOL_EVENT_MISSING")

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

echo "MCP_INGEST_TOOL_EVENT_ATTESTED_OK=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
