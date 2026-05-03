#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_attested_execute_replay_context_unknown"
SUMDIR="out/test_mcp_attested_execute_replay_context_unknown_out"
rm -rf "$TMP_ROOT" "$SUMDIR" out/mcp_exec out/mcp_attestation
mkdir -p "$TMP_ROOT" "$SUMDIR"

PRIVATE_PEM="$(cat "$ROOT/system/tests/fixtures/keys/ed25519_test_private.pem")"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" out/mcp_exec out/mcp_attestation
  mkdir -p "$TMP_ROOT"
  printf 'unknown context\n' > "$TMP_ROOT/src.txt"

  python3 - "$ROOT" "$PRIVATE_PEM" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
private_pem = sys.argv[2]
out_file = pathlib.Path(sys.argv[3])

req = {
    "id": "ATTEST_UNKNOWN",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_MOVE",
            "params": {
                "src_path": "out/test_mcp_attested_execute_replay_context_unknown/src.txt",
                "dst_path": "out/test_mcp_attested_execute_replay_context_unknown/dst.txt",
                "overwrite": True,
            },
        },
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": "RID_ATTEST_UNKNOWN_CTX",
            "attested": True,
            "signing_key": private_pem,
            "emit_replay_artifact": True,
            "replay_policy_context": "NO_SUCH",
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

if resp.get("executed") is not False:
    raise SystemExit("FAIL:EXECUTED_TRUE")
if resp.get("reason_token") != "POLICY_CONTEXT_UNKNOWN":
    raise SystemExit("FAIL:REASON_TOKEN")
replay = resp.get("replay_artifact", {})
if replay.get("present") is not False:
    raise SystemExit("FAIL:REPLAY_PRESENT")
if replay.get("reason_token") != "POLICY_CONTEXT_UNKNOWN":
    raise SystemExit("FAIL:REPLAY_REASON")
if replay.get("policy_context_used") != "NO_SUCH":
    raise SystemExit("FAIL:REPLAY_CONTEXT")

if (root / "out/test_mcp_attested_execute_replay_context_unknown/src.txt").exists() is False:
    raise SystemExit("FAIL:SRC_MOVED")
if (root / "out/test_mcp_attested_execute_replay_context_unknown/dst.txt").exists():
    raise SystemExit("FAIL:DST_CREATED")

summary = {
    "executed": resp.get("executed"),
    "reason_token": resp.get("reason_token"),
    "replay_artifact": replay,
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

echo "MCP_ATTESTED_EXECUTE_REPLAY_CONTEXT_UNKNOWN=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
