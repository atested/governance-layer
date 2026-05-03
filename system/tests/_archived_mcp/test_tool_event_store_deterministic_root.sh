#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_tool_event_store_deterministic_root"
OUT_DIR="out/test_tool_event_store_deterministic_root_out"
RUNTIME_DIR="$TMP_ROOT/runtime"
rm -rf "$TMP_ROOT" "$OUT_DIR" out/mcp_exec out/mcp_ingest_tool_event
mkdir -p "$TMP_ROOT" "$OUT_DIR"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" out/mcp_exec out/mcp_ingest_tool_event
  mkdir -p "$TMP_ROOT"

  GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 - "$ROOT" "$out_file" "$RUNTIME_DIR" <<'PY'
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])
runtime_dir = pathlib.Path(sys.argv[3])

sys.path.insert(0, str(root / "mcp"))
import tool_event_store as store

store_root = store.tool_event_store_root(root)
store_root_str = str(store_root).replace("\\", "/")
if "out/mcp_ingest_tool_event" in store_root_str:
    raise SystemExit("FAIL:STORE_ROOT_LEGACY_OUT")

params_digest = "sha256:" + hashlib.sha256(b"root-params").hexdigest()
output_digest = "sha256:" + hashlib.sha256(b"root-output").hexdigest()
req = {
    "id": "TOOL_EVENT_ROOT",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "INGEST_TOOL_EVENT",
            "params": {
                "tool_event_version": "v0",
                "tool_name": "TEST_TOOL_ROOT",
                "tool_params_digest": params_digest,
                "exit_code": 0,
                "outputs": [{"name": "stdout", "digest": output_digest, "ref_type": "blob"}],
                "provenance": {"source_identifier": "TEST_SRC", "extraction_date": "2026-03-06"},
                "policy_context_used": "DEFAULT",
            },
        },
        "mode": {"require_admissible": True, "dry_run": False, "run_id": "RID_TOOL_EVENT_ROOT"},
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
    raise SystemExit("FAIL:EXECUTE")
if resp.get("ingest_result", {}).get("TOOL_EVENT_STORE_COLLISION") != "NO":
    raise SystemExit("FAIL:COLLISION_EXPECTED_NO")

index_path = runtime_dir / "TOOL_EVENTS" / "index.v1.json"
if not index_path.is_file():
    raise SystemExit("FAIL:INDEX_MISSING")
index_body = index_path.read_bytes()

summary = {
    "store_root": store_root_str,
    "index_sha256": "sha256:" + hashlib.sha256(index_body).hexdigest(),
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$OUT_DIR/run1.json"
R2="$OUT_DIR/run2.json"
run_once "$R1"
run_once "$R2"

H1="$(shasum -a 256 "$R1" | awk '{print $1}')"
H2="$(shasum -a 256 "$R2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "TOOL_EVENT_STORE_DETERMINISTIC_ROOT=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
