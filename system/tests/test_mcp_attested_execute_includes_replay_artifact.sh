#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_attested_execute_includes_replay_artifact"
SUMDIR="out/test_mcp_attested_execute_includes_replay_artifact_out"
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
  printf 'attested replay move\n' > "$TMP_ROOT/src.txt"

  python3 - "$ROOT" "$PRIVATE_PEM" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
private_pem = sys.argv[2]
out_file = pathlib.Path(sys.argv[3])

req = {
    "id": "ATTEST_MOVE_REPLAY",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_MOVE",
            "params": {
                "src_path": "out/test_mcp_attested_execute_includes_replay_artifact/src.txt",
                "dst_path": "out/test_mcp_attested_execute_includes_replay_artifact/dst.txt",
                "overwrite": True,
            },
        },
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": "RID_ATTEST_REPLAY",
            "attested": True,
            "signing_key": private_pem,
            "emit_replay_artifact": True,
            "replay_policy_context": "DEFAULT",
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
if not (root / "out/test_mcp_attested_execute_includes_replay_artifact/dst.txt").exists():
    raise SystemExit("FAIL:DST_MISSING")

receipt = resp.get("receipt", {})
bundle = resp.get("attestation_bundle", {})
replay_artifact = resp.get("replay_artifact", {})

if replay_artifact.get("present") is not True:
    raise SystemExit("FAIL:REPLAY_ARTIFACT_ABSENT")
if replay_artifact.get("policy_context_used") != "DEFAULT":
    raise SystemExit("FAIL:REPLAY_CONTEXT")
if not str(replay_artifact.get("reason_token", "")):
    raise SystemExit("FAIL:REPLAY_TOKEN_EMPTY")
if replay_artifact.get("reason_token") == "POLICY_CONTEXT_UNKNOWN":
    raise SystemExit("FAIL:REPLAY_TOKEN_BAD")
if bundle.get("verified") is not True:
    raise SystemExit("FAIL:BUNDLE_NOT_VERIFIED")

artifact = root / "out/mcp_exec/RID_ATTEST_REPLAY/replay_check.v0.json"
if not artifact.is_file():
    raise SystemExit("FAIL:REPLAY_FILE_MISSING")
artifact_obj = json.loads(artifact.read_text(encoding="utf-8"))
if artifact_obj.get("policy_context_used") != "DEFAULT":
    raise SystemExit("FAIL:REPLAY_FILE_CONTEXT")

bundle_dir = root / str(bundle.get("bundle_dir", ""))
if not (bundle_dir / "payload/artifacts/replay_check.v0.json").is_file():
    raise SystemExit("FAIL:BUNDLE_REPLAY_FILE_MISSING")

vproc = subprocess.run(
    ["python3", str(root / "scripts/verify-attestation-bundle.py"), str(bundle_dir)],
    text=True,
    capture_output=True,
    check=False,
)
if vproc.returncode != 0:
    raise SystemExit("FAIL:VERIFY_RC")

summary = {
    "executed": resp.get("executed"),
    "reason_token": resp.get("reason_token"),
    "receipt_digest": receipt.get("digest"),
    "replay_artifact": replay_artifact,
    "bundle": {
        "present": bundle.get("present"),
        "verified": bundle.get("verified"),
        "bundle_dir": "out/mcp_attestation/RID_ATTEST_REPLAY",
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

echo "MCP_ATTESTED_EXECUTE_INCLUDES_REPLAY_ARTIFACT=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
