#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_tool_catalog_export_bundle"
OUT_SUM="$TMP_ROOT/out"
rm -rf "$TMP_ROOT" out/mcp_tool_catalog out/mcp_tool_catalog_bundles
mkdir -p "$OUT_SUM"

run_once() {
  local out_file="$1"
  rm -rf out/mcp_tool_catalog out/mcp_tool_catalog_bundles
  python3 - "$ROOT" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])
sys.path.insert(0, str(root / "mcp"))
from tool_catalog_store import put  # noqa: E402

put(root, {
    "tool_name": "mcp_export_one",
    "tool_version": "1.0.0",
    "schema_json": {"v": 1, "kind": "mcp_export"},
    "declared_capabilities": ["FS_COPY"],
    "created_from": "manual",
})

def rpc(req: dict) -> dict:
    proc = subprocess.run(
        ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
        input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("FAIL:RPC_RC")
    return json.loads(proc.stdout.strip())["result"]

res = rpc(
    {
        "id": "EXPORT",
        "method": "capabilities.tool_catalog_export_bundle",
        "params": {"sign": False},
    }
)
if res.get("ok") is not True:
    raise SystemExit("FAIL:EXPORT_NOT_OK")
bundle_id = str(res.get("bundle_id", ""))
if not bundle_id.startswith("tcb_"):
    raise SystemExit("FAIL:BUNDLE_ID")
if "/" in bundle_id:
    raise SystemExit("FAIL:PATH_LEAK")
manifest_sha = str(res.get("manifest_sha256", ""))
if not manifest_sha.startswith("sha256:"):
    raise SystemExit("FAIL:MANIFEST_SHA")
if res.get("signature_present") not in ("yes", "no"):
    raise SystemExit("FAIL:SIGNATURE_PRESENT")
summary = {
    "bundle_id": bundle_id,
    "manifest_sha256": manifest_sha,
    "signature_present": res.get("signature_present"),
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$OUT_SUM/run1.json"
R2="$OUT_SUM/run2.json"
run_once "$R1"
run_once "$R2"

H1="$(shasum -a 256 "$R1" | awk '{print $1}')"
H2="$(shasum -a 256 "$R2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_TOOL_CATALOG_EXPORT_BUNDLE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
