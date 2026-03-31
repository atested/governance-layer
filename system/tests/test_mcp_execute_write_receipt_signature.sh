#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_execute_write_receipt_signature"
OUT_DIR="out/test_mcp_execute_write_receipt_signature_out"
rm -rf "$TMP_ROOT" out/mcp_exec
mkdir -p "$TMP_ROOT"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

PRIVATE_PEM='-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIPFVBLmFaiKlEPwC2vjcA6z2OTsG0euiU2Gq4CzhG+7D
-----END PRIVATE KEY-----
'

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" out/mcp_exec
  mkdir -p "$TMP_ROOT"
  printf 'hello\n' > "$TMP_ROOT/src.txt"

  python3 - "$ROOT" "$PRIVATE_PEM" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
private_pem = sys.argv[2]
out_file = pathlib.Path(sys.argv[3])

req = {
    "id": "SIGWRITE",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_mcp_execute_write_receipt_signature/src.txt",
                "dst_path": "out/test_mcp_execute_write_receipt_signature/dst.txt",
                "overwrite": True,
            },
        },
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": "RID_SIGWRITE",
            "sign_receipt": True,
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
    raise SystemExit("FAIL:EXEC_RC")

payload = json.loads(proc.stdout.strip())["result"]
if payload.get("executed") is not True:
    raise SystemExit("FAIL:NOT_EXECUTED")
if payload.get("signature_present") is not True:
    raise SystemExit("FAIL:SIGNATURE_NOT_PRESENT")
if payload.get("signature_valid") is not True:
    raise SystemExit("FAIL:SIGNATURE_NOT_VALID")

rec_dir = root / "out/mcp_exec/RID_SIGWRITE"
sig_path = rec_dir / "action_record.sig"
meta_path = rec_dir / "action_record.sigmeta.json"
if not sig_path.exists() or not meta_path.exists():
    raise SystemExit("FAIL:SIGNATURE_FILES_MISSING")

meta = json.loads(meta_path.read_text(encoding="utf-8"))
if meta.get("digest") != payload.get("action_record_digest"):
    raise SystemExit("FAIL:DIGEST_MISMATCH")
if not str(meta.get("pubkey_fingerprint", "")).startswith("ed25519:"):
    raise SystemExit("FAIL:PUBKEY_FINGERPRINT")

out = {
    "action_record_digest": payload.get("action_record_digest"),
    "signature_present": payload.get("signature_present"),
    "signature_valid": payload.get("signature_valid"),
    "sig_len": len(sig_path.read_text(encoding="utf-8").strip()),
    "pubkey_fingerprint": meta.get("pubkey_fingerprint"),
}
out_file.write_text(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

RUN1="$OUT_DIR/run1.json"
RUN2="$OUT_DIR/run2.json"
run_once "$RUN1"
run_once "$RUN2"

H1="$(shasum -a 256 "$RUN1" | awk '{print $1}')"
H2="$(shasum -a 256 "$RUN2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_EXECUTE_WRITE_RECEIPT_SIG=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
