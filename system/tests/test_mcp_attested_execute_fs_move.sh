#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_attested_execute_fs_move"
SUMDIR="out/test_mcp_attested_execute_fs_move_out"
rm -rf "$TMP_ROOT" "$SUMDIR" out/mcp_exec out/mcp_attestation
mkdir -p "$TMP_ROOT" "$SUMDIR"

PRIVATE_PEM='-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIPFVBLmFaiKlEPwC2vjcA6z2OTsG0euiU2Gq4CzhG+7D
-----END PRIVATE KEY-----
'

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" out/mcp_exec out/mcp_attestation
  mkdir -p "$TMP_ROOT"
  printf 'attested move\n' > "$TMP_ROOT/src.txt"

  python3 - "$ROOT" "$PRIVATE_PEM" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
private_pem = sys.argv[2]
out_file = pathlib.Path(sys.argv[3])

req = {
    "id": "ATTEST_MOVE",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_MOVE",
            "params": {
                "src_path": "out/test_mcp_attested_execute_fs_move/src.txt",
                "dst_path": "out/test_mcp_attested_execute_fs_move/dst.txt",
                "overwrite": True,
            },
        },
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": "RID_ATTEST_MOVE",
            "attested": True,
            "signing_key": private_pem,
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
if (root / "out/test_mcp_attested_execute_fs_move/src.txt").exists():
    raise SystemExit("FAIL:SRC_STILL_EXISTS")
if not (root / "out/test_mcp_attested_execute_fs_move/dst.txt").exists():
    raise SystemExit("FAIL:DST_MISSING")

sig = resp.get("signature", {})
bundle = resp.get("attestation_bundle", {})
receipt = resp.get("receipt", {})
if sig.get("present") is not True or sig.get("valid") is not True:
    raise SystemExit("FAIL:SIGNATURE_STATE")
if bundle.get("present") is not True or bundle.get("verified") is not True:
    raise SystemExit("FAIL:BUNDLE_STATE")
if not str(bundle.get("bundle_dir", "")).startswith("out/"):
    raise SystemExit("FAIL:BUNDLE_DIR")
if not str(receipt.get("digest", "")).startswith("sha256:"):
    raise SystemExit("FAIL:RECEIPT_DIGEST")

bundle_dir = root / bundle["bundle_dir"]
if not (bundle_dir / "manifest.json").is_file():
    raise SystemExit("FAIL:BUNDLE_MANIFEST_MISSING")

summary = {
    "executed": resp.get("executed"),
    "reason_token": resp.get("reason_token"),
    "receipt_digest": receipt.get("digest"),
    "signature": sig,
    "attestation_bundle": {
        "present": bundle.get("present"),
        "verified": bundle.get("verified"),
        "bundle_dir": "out/mcp_attestation/RID_ATTEST_MOVE",
    },
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

echo "MCP_ATTESTED_EXECUTE_FS_MOVE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
