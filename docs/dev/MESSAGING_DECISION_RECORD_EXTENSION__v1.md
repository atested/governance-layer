# Messaging Decision Record Extension v1

## Objective

Specify additive decision-record fields for messaging invocations so later implementation can record canonical destination identity, mapping linkage, and opaque forwarding basis without introducing content-bearing fields.

## Additive Extension Strategy

The existing decision-record baseline in `docs/DECISION-RECORD.md` remains authoritative.

Messaging should extend it additively through:

- `governed_surface`
- messaging-specific `normalized_args`
- messaging-specific `policy_inputs`

No content-bearing payload fields should be introduced.

## Proposed Additive Fields

### `governed_surface`

- type: string
- required for messaging records
- value: `"messaging_proof_surface.v1"`

### `normalized_args`

Messaging records should add or populate:

- `messaging_map_hash`
  - string
  - authoritative hash of the explicit messaging binding map used for evaluation and replay
- `surface_binding_id`
  - string
- `mapping_version`
  - string
- `canonical_destination_kind`
  - string
- `canonical_destination_id`
  - string
- `raw_destination_input_kind`
  - string
- `raw_destination_input_value`
  - string
- `opaque_payload_handle_present`
  - boolean
- `opaque_payload_handle`
  - string
- `opaque_payload_transport`
  - string
- `opaque_payload_byte_length`
  - integer
- `reply_target_kind`
  - string, `MSG_REPLY` only
- `reply_target_id`
  - string, `MSG_REPLY` only

### `policy_inputs`

Messaging records should add or populate:

- `surface_binding_id`
- `mapping_version`
- `canonical_destination`
- `decision_alphabet`
  - fixed to `["ALLOW", "DENY"]`
- `content_visible_to_evaluator`
  - fixed to `false`

## Messaging Record Skeleton

```json
{
  "record_version": "0.2",
  "tool": "MSG_SEND",
  "capability_class": "MSG_SEND",
  "governed_surface": "messaging_proof_surface.v1",
  "messaging_map_hash": "sha256:...",
  "policy_decision": "ALLOW",
  "policy_reasons": [],
  "intent": {
    "goal": "send governed notification",
    "requested_action": "MSG_SEND",
    "expected_outputs": [
      "opaque payload forwarded after ALLOW"
    ]
  },
  "normalized_args": {
    "surface_binding_id": "msg.slack.chat.postMessage.v1",
    "mapping_version": "1",
    "canonical_destination_kind": "slack_channel",
    "canonical_destination_id": "slack://team/T123/channel/C456",
    "raw_destination_input_kind": "channel_alias",
    "raw_destination_input_value": "#deploy-alerts",
    "opaque_payload_handle_present": true,
    "opaque_payload_handle": "msgpayload://repo-rel/out/example/payload.bin",
    "opaque_payload_transport": "opaque_file_handle.v1",
    "opaque_payload_byte_length": 412
  },
  "policy_inputs": {
    "surface_binding_id": "msg.slack.chat.postMessage.v1",
    "mapping_version": "1",
    "canonical_destination": {
      "kind": "slack_channel",
      "id": "slack://team/T123/channel/C456"
    },
    "decision_alphabet": [
      "ALLOW",
      "DENY"
    ],
    "content_visible_to_evaluator": false
  }
}
```

## Decision-Record Rules

### Rule 1: Canonical destination is authoritative

`normalized_args.canonical_destination_id` is the replay anchor for destination identity.

### Rule 2: Raw destination is audit-only

`raw_destination_input_value` may be retained for audit and discrepancy analysis, but evaluator outcome must be based on canonical destination identity.

### Rule 3: Payload remains opaque

Decision records may indicate payload handle, transport, and bounded byte length, but must not record:

- body text
- subject text
- attachment filenames
- attachment content hashes that imply semantic inspection

### Rule 3a: Forwarding-phase replay strengthening

TASK_399 adopted Gap B Option 1 at slice 1, but TASK_400 upgrades replay binding without widening evaluator visibility:

- decision records still bind only `opaque_payload_handle` plus `opaque_payload_byte_length`
- decision records still do not bind payload bytes or payload hashes
- stronger payload binding now lives only in the post-`ALLOW` forwarding receipt
- replay may verify that forwarding receipt against the current opaque payload handle, but the receipt remains outside evaluator-facing schema

### Rule 4: Reply remains structural

`MSG_REPLY` records may record reply-target identity linkage, but not quoted content.

### Rule 5: No UNDECIDED

Messaging decision records may not use `UNDECIDED`.

## Forwarding Linkage Note

The forwarding receipt should link back to the decision record through:

- record hash
- request id
- surface binding id
- canonical destination id
- opaque payload handle
- opaque payload byte length
- payload digest for the bytes actually forwarded

That linkage is downstream of the evaluation decision and does not widen the evaluator-facing contract.
