#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_ingest_artifact_rejects_large_payload"
SUMDIR="out/test_mcp_ingest_artifact_rejects_large_payload_out"
rm -rf "$TMP_ROOT" "$SUMDIR" out/mcp_exec out/mcp_ingest
mkdir -p "$TMP_ROOT" "$SUMDIR"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" out/mcp_exec out/mcp_ingest
  mkdir -p "$TMP_ROOT"

  python3 - "$ROOT" "$out_file" <<'PY'
import base64
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])

raw = b"A" * 5000
payload = base64.b64encode(raw).decode("ascii")

req = {
    "id": "INGEST_LARGE",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "INGEST_ARTIFACT",
            "params": {
                "payload_b64": payload,
                "provenance": {
                    "source_identifier": "TEST_SRC",
                    "extraction_date": "2026-03-06",
                },
            },
        },
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": "RID_INGEST_LARGE",
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
    raise SystemExit("FAIL:EXECUTED_UNEXPECTED")
if resp.get("reason_token") != "ARTIFACT_TOO_LARGE":
    raise SystemExit("FAIL:WRONG_TOKEN")

summary = {
    "executed": resp.get("executed"),
    "admissible": resp.get("admissible"),
    "reason_token": resp.get("reason_token"),
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

echo "MCP_INGEST_ARTIFACT_REJECTS_LARGE_PAYLOAD=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
