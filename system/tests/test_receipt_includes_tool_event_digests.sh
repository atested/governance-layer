#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_receipt_includes_tool_event_digests"
RUNTIME_DIR="$TMP_ROOT/runtime"
RESULT_DIR="out/test_receipt_includes_tool_event_digests_results"
rm -rf "$TMP_ROOT" out/mcp_exec out/mcp_ingest_tool_event
rm -rf "$RESULT_DIR"
mkdir -p "$TMP_ROOT" "$RESULT_DIR"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" out/mcp_exec out/mcp_ingest_tool_event
  mkdir -p "$TMP_ROOT"

  GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 - "$ROOT" "$out_file" <<'PY'
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])
run_id = "RID_RECEIPT_TOOL_EVENT_DIGESTS"


def rpc(req):
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


tool_params_digest = "sha256:" + hashlib.sha256(b"receipt-linkage-params").hexdigest()
tool_output_digest = "sha256:" + hashlib.sha256(b"receipt-linkage-output").hexdigest()
req = {
    "id": "INGEST_TE",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "INGEST_TOOL_EVENT",
            "params": {
                "tool_event_version": "v0",
                "tool_name": "TEST_TOOL_EVENT_RECEIPT_LINK",
                "tool_params_digest": tool_params_digest,
                "exit_code": 0,
                "outputs": [{"name": "stdout", "digest": tool_output_digest, "ref_type": "blob"}],
                "provenance": {"source_identifier": "TEST_SRC", "extraction_date": "2026-03-06"},
                "policy_context_used": "DEFAULT",
            },
        },
        "mode": {"require_admissible": True, "dry_run": False, "run_id": run_id},
    },
}
res = rpc(req)
if res.get("executed") is not True:
    raise SystemExit("FAIL:EXECUTE_NOT_OK")
expected_digest = str(res.get("ingest_result", {}).get("tool_event_sha256", ""))
if not expected_digest.startswith("sha256:"):
    raise SystemExit("FAIL:MISSING_TOOL_EVENT_DIGEST")

record_path = root / "out" / "mcp_exec" / run_id / "action_record.json"
if not record_path.is_file():
    raise SystemExit("FAIL:RECEIPT_RECORD_MISSING")
record = json.loads(record_path.read_text(encoding="utf-8"))
digests = record.get("tool_event_digests")
if not isinstance(digests, list) or len(digests) < 1:
    raise SystemExit("FAIL:TOOL_EVENT_DIGESTS_MISSING")
if digests != sorted(set(digests)):
    raise SystemExit("FAIL:TOOL_EVENT_DIGESTS_NOT_SORTED_UNIQUE")
if expected_digest not in digests:
    raise SystemExit("FAIL:TOOL_EVENT_DIGEST_NOT_LINKED")

summary = {
    "run_id": run_id,
    "linked_digests": digests,
    "expected_digest": expected_digest,
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$RESULT_DIR/run1.json"
R2="$RESULT_DIR/run2.json"
run_once "$R1"
run_once "$R2"

H1="$(shasum -a 256 "$R1" | awk '{print $1}')"
H2="$(shasum -a 256 "$R2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "RECEIPT_INCLUDES_TOOL_EVENT_DIGESTS=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
