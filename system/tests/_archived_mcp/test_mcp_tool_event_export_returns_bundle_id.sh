#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_event_contract_common.sh"
tool_event_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_mcp_tool_event_export_returns_bundle_id"
OUT_DIR="out/test_mcp_tool_event_export_returns_bundle_id_out"
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


params_digest = "sha256:" + hashlib.sha256(b"tool-event-export-params").hexdigest()
out_digest = "sha256:" + hashlib.sha256(b"tool-event-export-output").hexdigest()
ingest_req = {
    "id": "INGEST_EXPORT_BUNDLE",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "INGEST_TOOL_EVENT",
            "params": {
                "tool_event_version": "v0",
                "tool_name": "TEST_TOOL_EVENT_EXPORT",
                "tool_params_digest": params_digest,
                "exit_code": 0,
                "outputs": [{"name": "stdout", "digest": out_digest, "ref_type": "blob"}],
                "provenance": {"source_identifier": "TEST_SRC", "extraction_date": "2026-03-06"},
                "policy_context_used": "DEFAULT",
            },
        },
        "mode": {"require_admissible": True, "dry_run": False, "run_id": "RID_TOOL_EVENT_EXPORT"},
    },
}
res = rpc(ingest_req)
if res.get("executed") is not True:
    raise SystemExit("FAIL:INGEST_EXEC")
digest = str(res["ingest_result"]["tool_event_sha256"])

exp = rpc(
    {
        "id": "EXPORT1",
        "method": "capabilities.tool_event_export",
        "params": {"digest": digest},
    }
)
if exp.get("ok") is not True:
    raise SystemExit("FAIL:EXPORT_NOT_OK")
bundle_id = str(exp.get("bundle_id", ""))
manifest_sha = str(exp.get("manifest_sha256", ""))
if not bundle_id.startswith("teb_"):
    raise SystemExit("FAIL:BUNDLE_ID_FORMAT")
if "/" in bundle_id or "/" in manifest_sha:
    raise SystemExit("FAIL:PATH_LEAK")
if not manifest_sha.startswith("sha256:"):
    raise SystemExit("FAIL:MANIFEST_SHA")
if int(exp.get("tool_event_digests_count", 0)) != 1:
    raise SystemExit("FAIL:DIGEST_COUNT")
if exp.get("POLICY_BYPASS") != "READ_ONLY_QUERY":
    raise SystemExit("FAIL:POLICY_BYPASS")

summary = {
    "bundle_id": bundle_id,
    "manifest_sha256": manifest_sha,
    "tool_event_digests_count": int(exp.get("tool_event_digests_count", 0)),
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$OUT_DIR/run1.json"
R2="$OUT_DIR/run2.json"
run_once "$R1"
run_once "$R2"

H1="$(shasum -a 256 "$R1" | awk '{print $1}')"
H2="$(shasum -a 256 "$R2" | awk '{print $1}')"
tool_event_require_equal "$H1" "$H2" "FAIL:NON_DETERMINISTIC"

echo "MCP_TOOL_EVENT_EXPORT_RETURNS_BUNDLE_ID=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
