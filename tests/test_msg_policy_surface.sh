#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
REPLAY="$ROOT/scripts/replay-record.py"
TMP_ROOT="$ROOT/out/test_msg_policy_surface"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT"

PAYLOAD_PATH_REL="out/test_msg_policy_surface/payload.bin"
PAYLOAD_PATH="$ROOT/$PAYLOAD_PATH_REL"
printf 'alpha001' > "$PAYLOAD_PATH"
PAYLOAD_HANDLE="msgpayload://repo-rel/$PAYLOAD_PATH_REL"
PAYLOAD_LEN="$(wc -c < "$PAYLOAD_PATH" | tr -d ' ')"

BASE_SEND="$TMP_ROOT/base_send.json"
BASE_REPLY="$TMP_ROOT/base_reply.json"

cat > "$BASE_SEND" <<JSON
{
  "tool": "MSG_SEND",
  "args": {
    "surface_binding_id": "msg.slack.chat.postMessage.v1",
    "mapping_version": "1",
    "canonical_destination": {
      "kind": "slack_channel",
      "id": "slack://workspace/default/channel/deploy-alerts"
    },
    "raw_destination_input": {
      "kind": "channel_alias",
      "value": "#deploy-alerts"
    },
    "opaque_payload": {
      "payload_handle": "$PAYLOAD_HANDLE",
      "byte_length": $PAYLOAD_LEN,
      "transport": "opaque_file_handle.v1"
    },
    "audit_scope": {
      "intent_label": "deploy-status",
      "justification_ref": "OPS-399",
      "rate_window_count": 1
    }
  },
  "intent": {
    "goal": "send governed deployment status notification",
    "constraints": {
      "content_visible_to_evaluator": false,
      "forwarding_evidence_binding": "payload digest captured only in post-ALLOW forwarding receipt"
    },
    "requested_action": "MSG_SEND",
    "expected_outputs": [
      {
        "ref": "message:forward_result",
        "value": "slack://workspace/default/channel/deploy-alerts"
      }
    ]
  }
}
JSON

cat > "$BASE_REPLY" <<JSON
{
  "tool": "MSG_REPLY",
  "args": {
    "surface_binding_id": "msg.smtp.reply.v1",
    "mapping_version": "1",
    "canonical_destination": {
      "kind": "email_reply_target",
      "id": "email://account/support@example.com/thread/1842/message/991"
    },
    "raw_destination_input": {
      "kind": "message_id_header",
      "value": "<991@example.test>"
    },
    "opaque_payload": {
      "payload_handle": "$PAYLOAD_HANDLE",
      "byte_length": $PAYLOAD_LEN,
      "transport": "opaque_file_handle.v1"
    },
    "reply_context": {
      "reply_target_kind": "email_message",
      "reply_target_id": "email://account/support@example.com/thread/1842/message/991"
    },
    "audit_scope": {
      "intent_label": "support-reply",
      "justification_ref": "OPS-399",
      "rate_window_count": 1
    }
  },
  "intent": {
    "goal": "reply through governed support surface",
    "constraints": {
      "content_visible_to_evaluator": false,
      "forwarding_evidence_binding": "payload digest captured only in post-ALLOW forwarding receipt"
    },
    "requested_action": "MSG_REPLY",
    "expected_outputs": [
      {
        "ref": "message:forward_result",
        "value": "email://account/support@example.com/thread/1842/message/991"
      }
    ]
  }
}
JSON

emit_req() {
  local base="$1"
  local out="$2"
  local patch_json="$3"
  python3 - "$base" "$out" "$patch_json" <<'PY'
import json
import sys

base_path, out_path, patch_json = sys.argv[1:4]
base = json.load(open(base_path, encoding="utf-8"))
patch = json.loads(patch_json)

def merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            merge(dst[k], v)
        else:
            dst[k] = v

merge(base, patch)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(base, f, indent=2, sort_keys=True)
    f.write("\n")
PY
}

json_expr() {
  python3 - "$1" "$2" <<'PY'
import json, sys
path, expr = sys.argv[1:3]
obj = json.load(open(path, encoding="utf-8"))
value = eval(expr, {}, {"obj": obj})
if isinstance(value, (dict, list)):
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))
else:
    print(value)
PY
}

assert_code() {
  local name="$1" file="$2" code="$3"
  python3 - "$file" "$code" "$name" <<'PY'
import json, sys
path, code, name = sys.argv[1:4]
obj = json.load(open(path, encoding="utf-8"))
codes = [r.get("code") for r in obj.get("policy_reasons", []) if isinstance(r, dict)]
if code not in codes:
    raise SystemExit(f"FAIL: {name} missing {code}; got {codes}")
print(f"PASS: {name}")
PY
}

assert_decision() {
  local name="$1" file="$2" want="$3"
  python3 - "$file" "$want" "$name" <<'PY'
import json, sys
path, want, name = sys.argv[1:4]
obj = json.load(open(path, encoding="utf-8"))
got = obj.get("policy_decision")
if got != want:
    raise SystemExit(f"FAIL: {name} decision {got} != {want}")
print(f"PASS: {name}")
PY
}

REQ_A="$TMP_ROOT/content_a.json"
REQ_B="$TMP_ROOT/content_b.json"
OUT_A="$TMP_ROOT/content_a.record.json"
OUT_B="$TMP_ROOT/content_b.record.json"
emit_req "$BASE_SEND" "$REQ_A" '{}'
python3 "$EVAL" "$REQ_A" > "$OUT_A"
printf 'omega999' > "$PAYLOAD_PATH"
emit_req "$BASE_SEND" "$REQ_B" '{}'
python3 "$EVAL" "$REQ_B" > "$OUT_B"
python3 - "$OUT_A" "$OUT_B" <<'PY'
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8"))
b = json.load(open(sys.argv[2], encoding="utf-8"))
assert a["policy_decision"] == "ALLOW"
assert b["policy_decision"] == "ALLOW"
assert a["normalized_args"] == b["normalized_args"]
assert a["policy_reasons"] == b["policy_reasons"] == []
assert "payload_hash" not in json.dumps(a["normalized_args"], sort_keys=True)
assert "body" not in json.dumps(a["policy_inputs"], sort_keys=True)
print("PASS: T-MSG-CONTENT-001 explicit content indifference")
PY

REQ_RAW="$TMP_ROOT/raw_destination_variation.json"
OUT_RAW="$TMP_ROOT/raw_destination_variation.record.json"
emit_req "$BASE_SEND" "$REQ_RAW" '{"args":{"raw_destination_input":{"value":"#ops-alias"}}}'
python3 "$EVAL" "$REQ_RAW" > "$OUT_RAW"
python3 - "$OUT_A" "$OUT_RAW" <<'PY'
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8"))
b = json.load(open(sys.argv[2], encoding="utf-8"))
assert a["policy_decision"] == b["policy_decision"] == "ALLOW"
assert a["normalized_args"]["canonical_destination_id"] == b["normalized_args"]["canonical_destination_id"]
assert a["normalized_args"]["raw_destination_input_value"] != b["normalized_args"]["raw_destination_input_value"]
print("PASS: T-MSG-DEST-001 canonical destination remains authoritative")
PY

REQ_CONTENT_FIELD="$TMP_ROOT/content_field.json"
OUT_CONTENT_FIELD="$TMP_ROOT/content_field.record.json"
emit_req "$BASE_SEND" "$REQ_CONTENT_FIELD" '{"args":{"body":"forbidden"}}'
python3 "$EVAL" "$REQ_CONTENT_FIELD" > "$OUT_CONTENT_FIELD"
assert_decision "T-MSG-CONTENT-002 decision" "$OUT_CONTENT_FIELD" "DENY"
assert_code "T-MSG-CONTENT-002 code" "$OUT_CONTENT_FIELD" "RC-MSG-CONTENT-FIELD-PRESENT"
python3 - "$OUT_CONTENT_FIELD" <<'PY'
import json, sys
obj = json.load(open(sys.argv[1], encoding="utf-8"))
assert obj.get("request_bytes_b64") is None
blob = json.dumps(obj, sort_keys=True)
assert "forbidden" not in blob
print("PASS: T-MSG-CONTENT-003 denied content not retained in governed record")
PY

REQ_UNKNOWN="$TMP_ROOT/unknown_binding.json"
OUT_UNKNOWN="$TMP_ROOT/unknown_binding.record.json"
emit_req "$BASE_SEND" "$REQ_UNKNOWN" '{"args":{"surface_binding_id":"msg.unknown.binding.v1"}}'
python3 "$EVAL" "$REQ_UNKNOWN" > "$OUT_UNKNOWN"
assert_code "T-MSG-MAP-001 code" "$OUT_UNKNOWN" "RC-MSG-UNKNOWN-SURFACE-BINDING"

REQ_VERSION="$TMP_ROOT/version_mismatch.json"
OUT_VERSION="$TMP_ROOT/version_mismatch.record.json"
emit_req "$BASE_SEND" "$REQ_VERSION" '{"args":{"mapping_version":"999"}}'
python3 "$EVAL" "$REQ_VERSION" > "$OUT_VERSION"
assert_code "T-MSG-MAP-002 code" "$OUT_VERSION" "RC-MSG-MAPPING-VERSION-MISMATCH"

REQ_CAP="$TMP_ROOT/capability_mismatch.json"
OUT_CAP="$TMP_ROOT/capability_mismatch.record.json"
emit_req "$BASE_SEND" "$REQ_CAP" '{"args":{"surface_binding_id":"msg.smtp.reply.v1"}}'
python3 "$EVAL" "$REQ_CAP" > "$OUT_CAP"
assert_code "T-MSG-MAP-003 code" "$OUT_CAP" "RC-MSG-CAPABILITY-MAPPING-MISMATCH"

REQ_MISSING_DEST="$TMP_ROOT/missing_destination.json"
OUT_MISSING_DEST="$TMP_ROOT/missing_destination.record.json"
emit_req "$BASE_SEND" "$REQ_MISSING_DEST" '{"args":{"canonical_destination":{"kind":"","id":""}}}'
python3 "$EVAL" "$REQ_MISSING_DEST" > "$OUT_MISSING_DEST"
assert_code "T-MSG-DEST-002 code" "$OUT_MISSING_DEST" "RC-MSG-CANONICAL-DESTINATION-MISSING"

REQ_KIND="$TMP_ROOT/kind_mismatch.json"
OUT_KIND="$TMP_ROOT/kind_mismatch.record.json"
emit_req "$BASE_SEND" "$REQ_KIND" '{"args":{"canonical_destination":{"kind":"email_reply_target"}}}'
python3 "$EVAL" "$REQ_KIND" > "$OUT_KIND"
assert_code "T-MSG-DEST-003 code" "$OUT_KIND" "RC-MSG-CANONICAL-DESTINATION-KIND-MISMATCH"

REQ_INTENT="$TMP_ROOT/missing_intent.json"
OUT_INTENT="$TMP_ROOT/missing_intent.record.json"
emit_req "$BASE_SEND" "$REQ_INTENT" '{"intent":{"goal":"","expected_outputs":[]}}'
python3 "$EVAL" "$REQ_INTENT" > "$OUT_INTENT"
assert_code "T-MSG-RC-001 code" "$OUT_INTENT" "RC-MSG-MISSING-INTENT-FIELDS"

REQ_DEST_DIS="$TMP_ROOT/destination_disallowed.json"
OUT_DEST_DIS="$TMP_ROOT/destination_disallowed.record.json"
emit_req "$BASE_SEND" "$REQ_DEST_DIS" '{"args":{"canonical_destination":{"id":"slack://workspace/other/channel/private"}}}'
python3 "$EVAL" "$REQ_DEST_DIS" > "$OUT_DEST_DIS"
assert_code "T-MSG-RC-002 code" "$OUT_DEST_DIS" "RC-MSG-DESTINATION-DISALLOWED"

REQ_CLASS_DIS="$TMP_ROOT/destination_class_disallowed.json"
OUT_CLASS_DIS="$TMP_ROOT/destination_class_disallowed.record.json"
emit_req "$BASE_SEND" "$REQ_CLASS_DIS" '{"args":{"raw_destination_input":{"kind":"email_alias"}}}'
python3 "$EVAL" "$REQ_CLASS_DIS" > "$OUT_CLASS_DIS"
assert_code "T-MSG-RC-003 code" "$OUT_CLASS_DIS" "RC-MSG-DESTINATION-CLASS-DISALLOWED"

REQ_TRANSPORT="$TMP_ROOT/transport_unauthorized.json"
OUT_TRANSPORT="$TMP_ROOT/transport_unauthorized.record.json"
emit_req "$BASE_SEND" "$REQ_TRANSPORT" '{"args":{"opaque_payload":{"transport":"inline_payload.v1"}}}'
python3 "$EVAL" "$REQ_TRANSPORT" > "$OUT_TRANSPORT"
assert_code "T-MSG-RC-004 code" "$OUT_TRANSPORT" "RC-MSG-TRANSPORT-UNAUTHORIZED"

REQ_SIZE="$TMP_ROOT/payload_size_exceeded.json"
OUT_SIZE="$TMP_ROOT/payload_size_exceeded.record.json"
emit_req "$BASE_SEND" "$REQ_SIZE" '{"args":{"opaque_payload":{"byte_length":70000}}}'
python3 "$EVAL" "$REQ_SIZE" > "$OUT_SIZE"
assert_code "T-MSG-RC-005 code" "$OUT_SIZE" "RC-MSG-PAYLOAD-SIZE-EXCEEDED"

REQ_RATE="$TMP_ROOT/rate_exceeded.json"
OUT_RATE="$TMP_ROOT/rate_exceeded.record.json"
emit_req "$BASE_SEND" "$REQ_RATE" '{"args":{"audit_scope":{"rate_window_count":99}}}'
python3 "$EVAL" "$REQ_RATE" > "$OUT_RATE"
assert_code "T-MSG-RC-006 code" "$OUT_RATE" "RC-MSG-RATE-EXCEEDED"

REQ_REPLY="$TMP_ROOT/reply_allow.json"
OUT_REPLY="$TMP_ROOT/reply_allow.record.json"
emit_req "$BASE_REPLY" "$REQ_REPLY" '{}'
python3 "$EVAL" "$REQ_REPLY" > "$OUT_REPLY"
assert_decision "T-MSG-REPLY-001 decision" "$OUT_REPLY" "ALLOW"

REQ_REPLY_CTX="$TMP_ROOT/reply_context_missing.json"
OUT_REPLY_CTX="$TMP_ROOT/reply_context_missing.record.json"
emit_req "$BASE_REPLY" "$REQ_REPLY_CTX" '{"args":{"reply_context":{"reply_target_kind":"","reply_target_id":""}}}'
python3 "$EVAL" "$REQ_REPLY_CTX" > "$OUT_REPLY_CTX"
assert_code "T-MSG-REPLY-002 code" "$OUT_REPLY_CTX" "RC-MSG-REPLY-CONTEXT-MISSING"

REQ_REPLY_MISMATCH="$TMP_ROOT/reply_target_mismatch.json"
OUT_REPLY_MISMATCH="$TMP_ROOT/reply_target_mismatch.record.json"
emit_req "$BASE_REPLY" "$REQ_REPLY_MISMATCH" '{"args":{"reply_context":{"reply_target_id":"email://account/support@example.com/thread/1842/message/998"}}}'
python3 "$EVAL" "$REQ_REPLY_MISMATCH" > "$OUT_REPLY_MISMATCH"
assert_code "T-MSG-REPLY-003 code" "$OUT_REPLY_MISMATCH" "RC-MSG-REPLY-TARGET-MISMATCH"

ALT_MAP="$TMP_ROOT/messaging-map-invalid.json"
python3 - "$ROOT/capabilities/messaging-tool-map.v1.json" "$ALT_MAP" <<'PY'
import json, sys
src, dst = sys.argv[1:3]
doc = json.load(open(src, encoding="utf-8"))
doc["entries"][0]["allowed_decisions"] = ["ALLOW", "DENY", "UNDECIDED"]
json.dump(doc, open(dst, "w", encoding="utf-8"), indent=2, sort_keys=True)
open(dst, "a", encoding="utf-8").write("\n")
PY
REQ_ALPHA="$TMP_ROOT/decision_alphabet.json"
OUT_ALPHA="$TMP_ROOT/decision_alphabet.record.json"
emit_req "$BASE_SEND" "$REQ_ALPHA" '{}'
GOV_MESSAGING_MAP_PATH="$ALT_MAP" python3 "$EVAL" "$REQ_ALPHA" > "$OUT_ALPHA"
assert_code "T-MSG-DECISION-001 code" "$OUT_ALPHA" "RC-MSG-DECISION-ALPHABET-VIOLATION"

python3 "$REPLAY" "$OUT_A" >/dev/null
echo "PASS: T-MSG-REPLAY-001 replay succeeds for ALLOW record"

ALT_MAP_REPLAY="$TMP_ROOT/messaging-map-replay-drift.json"
python3 - "$ROOT/capabilities/messaging-tool-map.v1.json" "$ALT_MAP_REPLAY" <<'PY'
import json, sys
src, dst = sys.argv[1:3]
doc = json.load(open(src, encoding="utf-8"))
doc["entries"][0]["provider"] = "slack_drift"
json.dump(doc, open(dst, "w", encoding="utf-8"), indent=2, sort_keys=True)
open(dst, "a", encoding="utf-8").write("\n")
PY
set +e
REPLAY_OUT="$(GOV_MESSAGING_MAP_PATH="$ALT_MAP_REPLAY" python3 "$REPLAY" "$OUT_A" 2>&1)"
RC_REPLAY="$?"
set -e
[[ "$RC_REPLAY" == "1" ]] || { echo "FAIL: T-MSG-REPLAY-002 expected replay mismatch rc=1 got $RC_REPLAY"; exit 1; }
echo "$REPLAY_OUT" | rg 'messaging_map_hash' >/dev/null || { echo "FAIL: T-MSG-REPLAY-002 missing messaging_map_hash mismatch"; exit 1; }
echo "PASS: T-MSG-REPLAY-002 messaging map drift fails replay"

python3 - "$OUT_A" <<'PY'
import json, sys
obj = json.load(open(sys.argv[1], encoding="utf-8"))
assert obj["normalized_args"]["opaque_payload_handle"].startswith("msgpayload://repo-rel/")
assert obj["normalized_args"]["opaque_payload_byte_length"] == 8
blob = json.dumps(obj, sort_keys=True)
assert "payload_hash" not in blob
assert "payload_sha256" not in blob
assert '"body"' not in blob
print("PASS: T-MSG-GAPB-001 evaluator remains blind while stronger binding stays outside the decision record")
PY

echo "MSG_POLICY_SURFACE=PASS"
