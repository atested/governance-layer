#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_msg_surface"
RUNTIME="$TMP_ROOT/runtime"
rm -rf "$TMP_ROOT" out/messaging_proxy
mkdir -p "$TMP_ROOT"

PAYLOAD_REL="out/test_mcp_msg_surface/payload.bin"
printf 'slice399' > "$PAYLOAD_REL"
HANDLE="msgpayload://repo-rel/$PAYLOAD_REL"

python3 - "$ROOT" "$HANDLE" "$RUNTIME" <<'PY'
import importlib.util
import hashlib
import json
import os
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
handle = sys.argv[2]
runtime = pathlib.Path(sys.argv[3])
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
    raise SystemExit("FAIL:MSG_SEND_ALLOW")
forward = allow.get("message_forward_result", {})
meta_path = pathlib.Path(forward.get("forwarded_outbox_path", ""))
if not meta_path.exists():
    raise SystemExit("FAIL:MSG_SEND_FORWARD_METADATA")
receipt_path = pathlib.Path(forward.get("forward_receipt_path", ""))
if not receipt_path.exists():
    raise SystemExit("FAIL:MSG_SEND_FORWARD_RECEIPT")
payload_out = meta_path.parent / "payload.bin"
if not payload_out.exists():
    raise SystemExit("FAIL:MSG_SEND_FORWARD_PAYLOAD")
receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
if receipt.get("payload_sha256") != "sha256:" + hashlib.sha256(payload_out.read_bytes()).hexdigest():
    raise SystemExit("FAIL:MSG_SEND_FORWARD_RECEIPT_DIGEST")
record = allow.get("decision_record", {})
provider_evidence = forward.get("provider_evidence", {})
if provider_evidence.get("receipt_version") != "msg_forward_receipt.v1":
    raise SystemExit("FAIL:MSG_SEND_PROVIDER_EVIDENCE_VERSION")
if provider_evidence.get("record_hash") != record.get("record_hash"):
    raise SystemExit("FAIL:MSG_SEND_PROVIDER_EVIDENCE_RECORD_HASH")
if provider_evidence.get("payload_sha256") != receipt.get("payload_sha256"):
    raise SystemExit("FAIL:MSG_SEND_PROVIDER_EVIDENCE_DIGEST")
note = provider_evidence.get("binding_strength_note", "")
if "post-ALLOW forwarding evidence" not in note or "not provider-confirmed delivery" not in note:
    raise SystemExit("FAIL:MSG_SEND_PROVIDER_EVIDENCE_OVERCLAIM")

norm = record.get("normalized_args", {})
if "opaque_payload_handle" not in norm or "opaque_payload_byte_length" not in norm:
    raise SystemExit("FAIL:MSG_SEND_GAPB_FIELDS")
if "payload_hash" in json.dumps(record, sort_keys=True):
    raise SystemExit("FAIL:MSG_SEND_PAYLOAD_HASH_PRESENT")
if "payload_sha256" in json.dumps(record, sort_keys=True):
    raise SystemExit("FAIL:MSG_SEND_RECEIPT_DIGEST_IN_RECORD")

before = sorted((root / "out/messaging_proxy").glob("*/forward_request.json"))
deny = mod.msg_send(
    surface_binding_id="msg.slack.chat.postMessage.v1",
    mapping_version="1",
    canonical_destination_kind="slack_channel",
    canonical_destination_id="slack://workspace/other/channel/private",
    raw_destination_kind="channel_alias",
    raw_destination_value="#private",
    payload_handle=handle,
    payload_byte_length=8,
    transport="opaque_file_handle.v1",
)
if deny.get("policy_decision") != "DENY":
    raise SystemExit("FAIL:MSG_SEND_DENY")
after = sorted((root / "out/messaging_proxy").glob("*/forward_request.json"))
if before != after:
    raise SystemExit("FAIL:MSG_SEND_DENY_FORWARDED")
after_receipts = sorted((root / "out/messaging_proxy").glob("*/forward_receipt.json"))
if len(after_receipts) != len(before):
    raise SystemExit("FAIL:MSG_SEND_DENY_RECEIPT_WRITTEN")

reply = mod.msg_reply(
    surface_binding_id="msg.smtp.reply.v1",
    mapping_version="1",
    canonical_destination_kind="email_reply_target",
    canonical_destination_id="email://account/support@example.com/thread/1842/message/991",
    raw_destination_kind="message_id_header",
    raw_destination_value="<991@example.test>",
    reply_target_kind="email_message",
    reply_target_id="email://account/support@example.com/thread/1842/message/991",
    payload_handle=handle,
    payload_byte_length=8,
    transport="opaque_file_handle.v1",
)
if reply.get("policy_decision") != "ALLOW":
    raise SystemExit("FAIL:MSG_REPLY_ALLOW")
if not pathlib.Path(reply["message_forward_result"]["forwarded_outbox_path"]).exists():
    raise SystemExit("FAIL:MSG_REPLY_FORWARD_METADATA")
if not pathlib.Path(reply["message_forward_result"]["forward_receipt_path"]).exists():
    raise SystemExit("FAIL:MSG_REPLY_FORWARD_RECEIPT")
reply_evidence = reply["message_forward_result"].get("provider_evidence", {})
if reply_evidence.get("receipt_version") != "msg_forward_receipt.v1":
    raise SystemExit("FAIL:MSG_REPLY_PROVIDER_EVIDENCE_VERSION")

print("MCP_MSG_SURFACE=PASS")
PY
