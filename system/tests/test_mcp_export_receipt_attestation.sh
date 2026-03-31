#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_export_receipt_attestation"
OUT_A="out/test_mcp_export_receipt_attestation_A"
OUT_B="out/test_mcp_export_receipt_attestation_B"
OUT_SUMMARY="out/test_mcp_export_receipt_attestation_out"
rm -rf "$TMP_ROOT" "$OUT_A" "$OUT_B" "$OUT_SUMMARY" out/mcp_exec
mkdir -p "$TMP_ROOT" "$OUT_SUMMARY"

PRIVATE_PEM='-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIPFVBLmFaiKlEPwC2vjcA6z2OTsG0euiU2Gq4CzhG+7D
-----END PRIVATE KEY-----
'

run_once() {
  local out_dir="$1"
  local out_file="$2"

  rm -rf "$TMP_ROOT" "$out_dir" out/mcp_exec
  mkdir -p "$TMP_ROOT"
  printf 'mcp export\n' > "$TMP_ROOT/src.txt"

  python3 - "$ROOT" "$PRIVATE_PEM" "$out_dir" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
private_pem = sys.argv[2]
out_dir = sys.argv[3]
out_file = pathlib.Path(sys.argv[4])

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

exec_req = {
    "id": "MCP_EXPORT_EXEC",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_mcp_export_receipt_attestation/src.txt",
                "dst_path": "out/test_mcp_export_receipt_attestation/dst.txt",
                "overwrite": True,
            },
        },
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": "RID_MCP_EXPORT",
            "sign_receipt": True,
            "signing_key": private_pem,
        },
    },
}
exec_res = rpc(exec_req)
if exec_res.get("executed") is not True:
    raise SystemExit("FAIL:EXEC_NOT_EXECUTED")

export_req = {
    "id": "MCP_EXPORT",
    "method": "capabilities.export_attestation",
    "params": {
        "run_id": "RID_MCP_EXPORT",
        "out_dir": out_dir,
        "include_signature": True,
    },
}
export_res = rpc(export_req)
if export_res.get("ok") is not True:
    raise SystemExit("FAIL:EXPORT_NOT_OK")
if export_res.get("reason_token") != "NONE":
    raise SystemExit("FAIL:EXPORT_TOKEN")

bundle = root / out_dir
if not (bundle / "manifest.json").is_file():
    raise SystemExit("FAIL:MANIFEST_MISSING")
out = {
    "bundle_dir": "out/test_mcp_export_receipt_attestation_X",
    "ok": export_res.get("ok"),
    "reason_token": export_res.get("reason_token"),
    "manifest_sha": __import__("hashlib").sha256((bundle / "manifest.json").read_bytes()).hexdigest(),
}
out_file.write_text(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

N1="$OUT_SUMMARY/run1.json"
N2="$OUT_SUMMARY/run2.json"
run_once "$OUT_A" "$N1"
run_once "$OUT_B" "$N2"

H1="$(shasum -a 256 "$N1" | awk '{print $1}')"
H2="$(shasum -a 256 "$N2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_EXPORT_RECEIPT_ATTESTATION=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
