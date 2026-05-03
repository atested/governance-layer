#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_event_contract_common.sh"
tool_event_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_mcp_tool_event_bundle_verify"
OUT_DIR="out/test_mcp_tool_event_bundle_verify_out"
RUNTIME_DIR="$TMP_ROOT/runtime"
rm -rf "$TMP_ROOT" "$OUT_DIR" out/mcp_exec out/mcp_ingest_tool_event
mkdir -p "$TMP_ROOT" "$OUT_DIR"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" out/mcp_exec out/mcp_ingest_tool_event
  mkdir -p "$TMP_ROOT"

  GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 - "$ROOT" "$out_file" <<'PY'
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])


def rpc(req):
    proc = subprocess.run(
        ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
        input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("FAIL:RPC_RC")
    payload = json.loads(proc.stdout.strip())
    return payload["result"]


params_digest = "sha256:" + hashlib.sha256(b"tool-event-bundle-verify-params").hexdigest()
out_digest = "sha256:" + hashlib.sha256(b"tool-event-bundle-verify-output").hexdigest()
ingest_req = {
    "id": "INGEST_BUNDLE_VERIFY",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "INGEST_TOOL_EVENT",
            "params": {
                "tool_event_version": "v0",
                "tool_name": "TEST_TOOL_BUNDLE_VERIFY",
                "tool_params_digest": params_digest,
                "exit_code": 0,
                "outputs": [{"name": "stdout", "digest": out_digest, "ref_type": "blob"}],
                "provenance": {"source_identifier": "TEST_SRC", "extraction_date": "2026-03-06"},
                "policy_context_used": "DEFAULT",
            },
        },
        "mode": {"require_admissible": True, "dry_run": False, "run_id": "RID_TOOL_EVENT_BUNDLE_VERIFY"},
    },
}
ingest_res = rpc(ingest_req)
if ingest_res.get("executed") is not True:
    raise SystemExit("FAIL:INGEST_EXEC")
digest = str(ingest_res["ingest_result"]["tool_event_sha256"])

export_res = rpc(
    {
        "id": "EXPORT_BUNDLE",
        "method": "capabilities.tool_event_export",
        "params": {"digest": digest},
    }
)
if export_res.get("ok") is not True:
    raise SystemExit("FAIL:EXPORT_NOT_OK")
bundle_id = str(export_res.get("bundle_id", ""))
if not bundle_id.startswith("teb_"):
    raise SystemExit("FAIL:BUNDLE_ID")

verify_ok = rpc(
    {
        "id": "VERIFY_OK",
        "method": "capabilities.tool_event_bundle_verify",
        "params": {"bundle_id": bundle_id},
    }
)
if verify_ok.get("ok") is not True or verify_ok.get("reason") != "OK":
    raise SystemExit("FAIL:VERIFY_OK")
manifest_sha = str(verify_ok.get("manifest_sha256", ""))
if not manifest_sha.startswith("sha256:"):
    raise SystemExit("FAIL:MANIFEST_SHA")

payload_dir = root / "out/test_mcp_tool_event_bundle_verify/runtime/TOOL_EVENTS/BUNDLES" / bundle_id / "payload"
payload_files = sorted(payload_dir.glob("*.json"))
if len(payload_files) != 1:
    raise SystemExit("FAIL:PAYLOAD_COUNT")
data = bytearray(payload_files[0].read_bytes())
if not data:
    raise SystemExit("FAIL:PAYLOAD_EMPTY")
data[0] = (data[0] + 1) % 256
payload_files[0].write_bytes(bytes(data))

verify_bad = rpc(
    {
        "id": "VERIFY_BAD",
        "method": "capabilities.tool_event_bundle_verify",
        "params": {"bundle_id": bundle_id},
    }
)
if verify_bad.get("ok") is True:
    raise SystemExit("FAIL:VERIFY_BAD_OK")
if verify_bad.get("reason") != "HASH_MISMATCH":
    raise SystemExit("FAIL:VERIFY_BAD_REASON")

summary = {
    "bundle_id": bundle_id,
    "manifest_sha256": manifest_sha,
    "verify_ok_reason": str(verify_ok.get("reason", "")),
    "verify_bad_reason": str(verify_bad.get("reason", "")),
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$OUT_DIR/run1.json"
R2="$OUT_DIR/run2.json"
run_once "$R1"
run_once "$R2"

H1="$(tool_event_sha256_file "$R1")"
H2="$(tool_event_sha256_file "$R2")"
tool_event_require_equal "$H1" "$H2" "FAIL:NON_DETERMINISTIC"

echo "MCP_TOOL_EVENT_BUNDLE_VERIFY=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
