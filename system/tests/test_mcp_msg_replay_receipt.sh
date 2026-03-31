#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_msg_replay_receipt"
RUNTIME="$TMP_ROOT/runtime"
rm -rf "$TMP_ROOT" out/messaging_proxy
mkdir -p "$TMP_ROOT"

PAYLOAD_REL="out/test_mcp_msg_replay_receipt/payload.bin"
printf 'alpha001' > "$PAYLOAD_REL"
HANDLE="msgpayload://repo-rel/$PAYLOAD_REL"

python3 - "$ROOT" "$HANDLE" "$RUNTIME" "$TMP_ROOT/allow.record.json" <<'PY'
import importlib.util
import json
import os
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
handle = sys.argv[2]
runtime = pathlib.Path(sys.argv[3])
record_out = pathlib.Path(sys.argv[4])
os.environ["GOV_RUNTIME_DIR"] = str(runtime)
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root / "scripts"))

spec = importlib.util.spec_from_file_location("gov_mcp_server", root / "mcp/server.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

allow = mod.msg_send(
    surface_binding_id="msg.slack.chat.postMessage.v1",
    mapping_version="1",
    canonical_destination_kind="slack_channel",
    canonical_destination_id="slack://workspace/default/channel/deploy-alerts",
    raw_destination_kind="channel_alias",
    raw_destination_value="#deploy-alerts",
    payload_handle=handle,
    payload_byte_length=8,
    transport="opaque_file_handle.v1",
)
if allow.get("policy_decision") != "ALLOW":
    raise SystemExit("FAIL:MSG_REPLAY_RECEIPT_ALLOW")
record = allow.get("decision_record", {})
forward = allow.get("message_forward_result", {})
receipt_path = pathlib.Path(forward.get("forward_receipt_path", ""))
if not receipt_path.exists():
    raise SystemExit("FAIL:MSG_REPLAY_RECEIPT_MISSING")
provider_evidence = forward.get("provider_evidence", {})
if provider_evidence.get("payload_sha256") != json.loads(receipt_path.read_text(encoding="utf-8")).get("payload_sha256"):
    raise SystemExit("FAIL:MSG_REPLAY_PROVIDER_EVIDENCE_DIGEST")
record.pop("verification_state", None)
if "payload_sha256" in json.dumps(record, sort_keys=True):
    raise SystemExit("FAIL:MSG_REPLAY_RECEIPT_DIGEST_LEAK")
record_out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("MCP_MSG_REPLAY_RECEIPT_FIXTURE=PASS")
PY

REPLAY_PASS="$(python3 scripts/replay-record.py "$TMP_ROOT/allow.record.json" 2>&1)"
echo "$REPLAY_PASS" | rg 'PASS: replay matches original' >/dev/null || {
  echo "FAIL:MSG_REPLAY_RECEIPT_PASS"
  echo "$REPLAY_PASS"
  exit 1
}
echo "$REPLAY_PASS" | rg 'Messaging Receipt: ' >/dev/null || {
  echo "FAIL:MSG_REPLAY_RECEIPT_NOTE"
  echo "$REPLAY_PASS"
  exit 1
}

printf 'omega999' > "$PAYLOAD_REL"
set +e
REPLAY_FAIL="$(python3 scripts/replay-record.py "$TMP_ROOT/allow.record.json" 2>&1)"
RC="$?"
set -e
[[ "$RC" == "1" ]] || {
  echo "FAIL:MSG_REPLAY_RECEIPT_EXPECTED_MISMATCH"
  echo "$REPLAY_FAIL"
  exit 1
}
echo "$REPLAY_FAIL" | rg 'forward_receipt.payload_sha256' >/dev/null || {
  echo "FAIL:MSG_REPLAY_RECEIPT_MISMATCH_FIELD"
  echo "$REPLAY_FAIL"
  exit 1
}

echo "MCP_MSG_REPLAY_RECEIPT=PASS"
