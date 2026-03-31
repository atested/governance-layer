#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_tool_catalog_verify_bundle"
OUT_SUM="$TMP_ROOT/out"
rm -rf "$TMP_ROOT" out/mcp_tool_catalog out/mcp_tool_catalog_bundles
mkdir -p "$OUT_SUM"

PRIVATE_PEM='-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIPFVBLmFaiKlEPwC2vjcA6z2OTsG0euiU2Gq4CzhG+7D
-----END PRIVATE KEY-----
'
PUBLIC_PEM='-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAAag0f+gOBBZ4T3SxK6bGhC2IW4MhNHvvg8cWuUcOc6k=
-----END PUBLIC KEY-----
'

run_once() {
  local out_file="$1"
  rm -rf out/mcp_tool_catalog out/mcp_tool_catalog_bundles
  python3 - "$ROOT" "$out_file" "$PRIVATE_PEM" "$PUBLIC_PEM" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])
private_pem = sys.argv[3]
public_pem = sys.argv[4]
sys.path.insert(0, str(root / "mcp"))
from tool_catalog_store import put  # noqa: E402

put(root, {
    "tool_name": "mcp_verify_one",
    "tool_version": "1.0.0",
    "schema_json": {"v": 1, "kind": "mcp_verify"},
    "declared_capabilities": ["FS_MOVE"],
    "created_from": "external",
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

exp = rpc(
    {
        "id": "EXPORT",
        "method": "capabilities.tool_catalog_export_bundle",
        "params": {"sign": True, "private_key_ref": private_pem},
    }
)
if exp.get("ok") is not True:
    raise SystemExit("FAIL:EXPORT")
bundle_id = str(exp.get("bundle_id", ""))

ok = rpc(
    {
        "id": "VERIFY_OK",
        "method": "capabilities.tool_catalog_verify_bundle",
        "params": {"bundle_id": bundle_id, "require_signature": True, "pubkey": public_pem},
    }
)
if ok.get("ok") is not True or ok.get("reason") != "OK":
    raise SystemExit("FAIL:VERIFY_OK")
if ok.get("POLICY_BYPASS") != "READ_ONLY_QUERY":
    raise SystemExit("FAIL:BYPASS_TOKEN")

bundle_dir = root / "out" / "mcp_tool_catalog_bundles" / bundle_id
manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
target = bundle_dir / manifest["files"][0]["path"]
raw = bytearray(target.read_bytes())
raw[0] = (raw[0] + 1) % 256
target.write_bytes(bytes(raw))

bad = rpc(
    {
        "id": "VERIFY_BAD",
        "method": "capabilities.tool_catalog_verify_bundle",
        "params": {"bundle_id": bundle_id, "require_signature": False},
    }
)
if bad.get("ok") is not False:
    raise SystemExit("FAIL:VERIFY_BAD_SHOULD_FAIL")
if bad.get("reason") != "HASH_MISMATCH":
    raise SystemExit("FAIL:BAD_REASON")

summary = {
    "bundle_id": bundle_id,
    "ok_reason": ok.get("reason"),
    "bad_reason": bad.get("reason"),
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

echo "MCP_TOOL_CATALOG_VERIFY_BUNDLE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
