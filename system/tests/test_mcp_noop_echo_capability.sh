#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_noop_echo_capability"
SUMDIR="out/test_mcp_noop_echo_capability_out"
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

  python3 - "$ROOT" "$PRIVATE_PEM" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
private_pem = sys.argv[2]
out_file = pathlib.Path(sys.argv[3])


def rpc(method: str, params: dict) -> dict:
    req = {"id": method, "method": method, "params": params}
    proc = subprocess.run(
        ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
        input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"FAIL:{method}:RPC")
    return json.loads(proc.stdout.strip())["result"]

caps = rpc("capabilities.list", {})
names = [c.get("name") for c in caps.get("capabilities", []) if isinstance(c, dict)]
if "NOOP_ECHO" not in names:
    raise SystemExit("FAIL:NOOP_NOT_LISTED")

desc = rpc("capabilities.describe", {"name": "NOOP_ECHO"})
if not desc.get("ok") or desc.get("name") != "NOOP_ECHO":
    raise SystemExit("FAIL:NOOP_DESCRIBE")

resp = rpc(
    "capabilities.execute",
    {
        "capabilities_version": "v0",
        "action": {"name": "NOOP_ECHO", "params": {"echo": "hello"}},
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": "RID_NOOP_ECHO",
            "attested": True,
            "signing_key": private_pem,
            "emit_replay_artifact": True,
            "replay_policy_context": "DEFAULT",
            "attestation_out_dir": "out/test_mcp_noop_echo_capability/attestation/RID_NOOP_ECHO",
        },
    },
)
if resp.get("executed") is not True:
    raise SystemExit("FAIL:NOOP_NOT_EXECUTED")
if resp.get("reason_token") != "NONE":
    raise SystemExit("FAIL:NOOP_REASON")
if resp.get("attestation_bundle", {}).get("verified") is not True:
    raise SystemExit("FAIL:NOOP_BUNDLE_VERIFY")

bundle_rel = "out/test_mcp_noop_echo_capability/attestation/RID_NOOP_ECHO"
vproc = subprocess.run(
    ["python3", str(root / "scripts/verify-attestation-bundle.py"), bundle_rel],
    text=True,
    capture_output=True,
    check=False,
)
if vproc.returncode != 0:
    raise SystemExit("FAIL:NOOP_VERIFY")

summary = {
    "listed": True,
    "described": True,
    "executed": resp.get("executed"),
    "reason_token": resp.get("reason_token"),
    "digest": resp.get("receipt", {}).get("digest", ""),
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

echo "MCP_NOOP_ECHO_CAPABILITY=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
