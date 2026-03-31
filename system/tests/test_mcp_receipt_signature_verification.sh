#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_receipt_signature_verification"
OUT_DIR="out/test_mcp_receipt_signature_verification_out"
rm -rf "$TMP_ROOT" "$OUT_DIR" out/mcp_exec
mkdir -p "$TMP_ROOT" "$OUT_DIR"

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
  rm -rf "$TMP_ROOT" out/mcp_exec
  mkdir -p "$TMP_ROOT"
  printf 'verify\n' > "$TMP_ROOT/src.txt"

  python3 - "$ROOT" "$PRIVATE_PEM" "$PUBLIC_PEM" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
private_pem = sys.argv[2]
public_pem = sys.argv[3]
out_file = pathlib.Path(sys.argv[4])


def call(req: dict) -> dict:
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
    "id": "EXEC",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_mcp_receipt_signature_verification/src.txt",
                "dst_path": "out/test_mcp_receipt_signature_verification/dst.txt",
                "overwrite": True,
            },
        },
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": "RID_SIGVERIFY",
            "sign_receipt": True,
            "signing_key": private_pem,
        },
    },
}

exec_res = call(exec_req)
if exec_res.get("executed") is not True:
    raise SystemExit("FAIL:EXEC_NOT_EXECUTED")

ok_req = {
    "id": "R_OK",
    "method": "capabilities.receipt",
    "params": {"run_id": "RID_SIGVERIFY", "verify_signature": True, "pubkey": public_pem},
}
ok_res = call(ok_req)
if ok_res.get("signature_valid") is not True:
    raise SystemExit("FAIL:VERIFY_EXPECTED_TRUE")

nopub_req = {
    "id": "R_NOPUB",
    "method": "capabilities.receipt",
    "params": {"run_id": "RID_SIGVERIFY", "verify_signature": True},
}
nopub_res = call(nopub_req)
if nopub_res.get("signature_reason_token") != "PUBKEY_MISSING":
    raise SystemExit("FAIL:PUBKEY_MISSING_EXPECTED")

sig_path = root / "out/mcp_exec/RID_SIGVERIFY/action_record.sig"
sig = sig_path.read_text(encoding="utf-8").strip()
if len(sig) < 4:
    raise SystemExit("FAIL:SIG_TOO_SHORT")
sig_path.write_text(("AAAA" + sig[4:]) + "\n", encoding="utf-8")

bad_req = {
    "id": "R_BAD",
    "method": "capabilities.receipt",
    "params": {"run_id": "RID_SIGVERIFY", "verify_signature": True, "pubkey": public_pem},
}
bad_res = call(bad_req)
if bad_res.get("signature_valid") is not False:
    raise SystemExit("FAIL:VERIFY_EXPECTED_FALSE")
if bad_res.get("signature_reason_token") != "SIGNATURE_INVALID":
    raise SystemExit("FAIL:SIGNATURE_INVALID_EXPECTED")

out = {
    "ok": {
        "signature_present": ok_res.get("signature_present"),
        "signature_valid": ok_res.get("signature_valid"),
        "signature_reason_token": ok_res.get("signature_reason_token"),
    },
    "nopub": {"signature_reason_token": nopub_res.get("signature_reason_token")},
    "bad": {
        "signature_valid": bad_res.get("signature_valid"),
        "signature_reason_token": bad_res.get("signature_reason_token"),
    },
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

echo "MCP_RECEIPT_SIGNATURE_VERIFICATION=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
