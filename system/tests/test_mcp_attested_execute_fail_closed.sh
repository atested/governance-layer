#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_attested_execute_fail_closed"
SUMDIR="out/test_mcp_attested_execute_fail_closed_out"
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
  printf 'blocked\n' > "$TMP_ROOT/src.txt"

  python3 - "$ROOT" "$PRIVATE_PEM" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
private_pem = sys.argv[2]
out_file = pathlib.Path(sys.argv[3])


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

# 1) Missing signing key => fail closed.
r1 = rpc({
    "id": "C1",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {"name": "FS_MOVE", "params": {"src_path": "out/test_mcp_attested_execute_fail_closed/src.txt", "dst_path": "out/test_mcp_attested_execute_fail_closed/dst.txt", "overwrite": True}},
        "mode": {"attested": True, "require_admissible": True, "dry_run": False, "run_id": "RID_FAIL_MISSING_KEY"}
    }
})
if r1.get("executed") is not False or r1.get("reason_token") != "SIGNING_KEY_MISSING":
    raise SystemExit("FAIL:CASE1")

# 2) Policy-blocked traversal => no signature/bundle.
r2 = rpc({
    "id": "C2",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {"name": "FS_MOVE", "params": {"src_path": "../bad.txt", "dst_path": "out/test_mcp_attested_execute_fail_closed/dst2.txt", "overwrite": True}},
        "mode": {"attested": True, "signing_key": private_pem, "require_admissible": True, "dry_run": False, "run_id": "RID_FAIL_POLICY"}
    }
})
if r2.get("executed") is not False:
    raise SystemExit("FAIL:CASE2_EXECUTED")
if r2.get("reason_token") != "PATH_TRAVERSAL":
    raise SystemExit("FAIL:CASE2_REASON")
if r2.get("signature", {}).get("present") is not False:
    raise SystemExit("FAIL:CASE2_SIG_PRESENT")
if r2.get("attestation_bundle", {}).get("present") is not False:
    raise SystemExit("FAIL:CASE2_BUNDLE_PRESENT")

# 3) Invalid attestation out dir triggers EXPORT_FAILED pre-exec.
r3 = rpc({
    "id": "C3",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {"name": "FS_MOVE", "params": {"src_path": "out/test_mcp_attested_execute_fail_closed/src.txt", "dst_path": "out/test_mcp_attested_execute_fail_closed/dst3.txt", "overwrite": True}},
        "mode": {"attested": True, "signing_key": private_pem, "attestation_out_dir": "tmp/not-under-out", "require_admissible": True, "dry_run": False, "run_id": "RID_FAIL_EXPORT"}
    }
})
if r3.get("executed") is not False or r3.get("reason_token") != "EXPORT_FAILED":
    raise SystemExit("FAIL:CASE3")
if r3.get("attestation_bundle", {}).get("reason_token") != "EXPORT_FAILED":
    raise SystemExit("FAIL:CASE3_TOKEN")

summary = {
    "case1": {"executed": r1.get("executed"), "reason_token": r1.get("reason_token")},
    "case2": {
        "executed": r2.get("executed"),
        "reason_token": r2.get("reason_token"),
        "signature_present": r2.get("signature", {}).get("present"),
        "bundle_present": r2.get("attestation_bundle", {}).get("present"),
    },
    "case3": {
        "executed": r3.get("executed"),
        "reason_token": r3.get("reason_token"),
        "bundle_reason": r3.get("attestation_bundle", {}).get("reason_token"),
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

echo "MCP_ATTESTED_EXECUTE_FAIL_CLOSED=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
