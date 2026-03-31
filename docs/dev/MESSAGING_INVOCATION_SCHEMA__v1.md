# Messaging Invocation Schema v1

## Objective

Define repo-ready canonical invocation objects for `MSG_SEND` and `MSG_REPLY` that preserve evaluator blindness, canonical destination authority, and ALLOW/DENY-only semantics.

## Shared Evaluator-Facing Shape

The evaluator-facing invocation object must use this shared top-level shape:

```json
{
  "tool": "MSG_SEND",
  "capability_class": "MSG_SEND",
  "args": {}
}
```

Top-level required fields:

- `tool`
- `capability_class`
- `args`

## Shared `args` Fields

### `surface_binding_id`

- type: string
- required
- authoritative link to explicit external-tool mapping entry

### `mapping_version`

- type: string
- required
- binds request to explicit mapping version

### `canonical_destination`

- type: object
- required
- authoritative destination identity used for evaluation and replay

Fields:
- `kind`: string
- `id`: string

### `raw_destination_input`

- type: object
- required
- preserved only for audit evidence

Fields:
- `kind`: string
- `value`: string

### `opaque_payload`

- type: object
- required
- payload transport metadata only

Fields:
- `payload_handle`: string
- `byte_length`: integer
- `transport`: string

The evaluator must not receive payload bytes, subject text, body text, attachment names, or attachment bytes.

### `intent`

- type: object
- required
- existing governance intent pattern, constrained to structural audit scoping

Required fields:
- `goal`
- `requested_action`
- `expected_outputs`

Optional:
- `constraints`

### `audit_scope`

- type: object
- optional
- structural scoping only

Recommended fields:
- `intent_label`: string
- `justification_ref`: string
- `rate_window_count`: integer

## `MSG_SEND`

### Required `args`

- all shared fields

### Forbidden `args`

- `reply_context`
- any content-bearing fields

### Example `MSG_SEND`

```json
{
  "tool": "MSG_SEND",
  "capability_class": "MSG_SEND",
  "args": {
    "surface_binding_id": "msg.slack.chat.postMessage.v1",
    "mapping_version": "1",
    "canonical_destination": {
      "kind": "slack_channel",
      "id": "slack://team/T123/channel/C456"
    },
    "raw_destination_input": {
      "kind": "channel_alias",
      "value": "#deploy-alerts"
    },
    "opaque_payload": {
      "payload_handle": "msgpayload://runtime/4e2f",
      "byte_length": 412,
      "transport": "opaque_file_handle.v1"
    },
    "intent": {
      "goal": "send governed deployment status notification",
      "requested_action": "MSG_SEND",
      "expected_outputs": [
        "opaque payload forwarded to mapped messaging provider after ALLOW"
      ],
      "constraints": [
        "content not evaluated by policy"
      ]
    },
    "audit_scope": {
      "intent_label": "deployment-status",
      "rate_window_count": 1
    }
  }
}
```

## `MSG_REPLY`

### Required `args`

- all shared fields
- `reply_context`

### `reply_context`

- type: object
- required for `MSG_REPLY`
- structural linkage only

Fields:
- `reply_target_kind`: string
- `reply_target_id`: string

`reply_target_id` must be structurally consistent with `canonical_destination.id`.

### Example `MSG_REPLY`

```json
{
  "tool": "MSG_REPLY",
  "capability_class": "MSG_REPLY",
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
      "payload_handle": "msgpayload://runtime/7ac1",
      "byte_length": 684,
      "transport": "opaque_file_handle.v1"
    },
    "reply_context": {
      "reply_target_kind": "email_message",
      "reply_target_id": "email://account/support@example.com/thread/1842/message/991"
    },
    "intent": {
      "goal": "reply through governed support surface",
      "requested_action": "MSG_REPLY",
      "expected_outputs": [
        "opaque reply payload forwarded after ALLOW"
      ],
      "constraints": [
        "content not evaluated by policy"
      ]
    },
    "audit_scope": {
      "intent_label": "support-reply",
      "rate_window_count": 1
    }
  }
}
```

## Structural Blindness Rules

Evaluator-facing invocation schemas must reject fields such as:

- `body`
- `text`
- `subject`
- `html`
- `attachments`
- `quoted_text`
- `rendered_preview`

This prohibition is constitutive to `INV-M2`.

## Canonical Replay Rules

Replay should be keyed by:

- `tool`
- `capability_class`
- `surface_binding_id`
- `mapping_version`
- `canonical_destination.kind`
- `canonical_destination.id`
- `reply_context.reply_target_id` for `MSG_REPLY`

Replay must not re-evaluate against raw destination input.

## ALLOW / DENY Rule

Messaging invocation outputs must use:

- `ALLOW`
- `DENY`

`UNDECIDED` is invalid for this proof surface.

## TASK_399 Slice-1 Gap B Choice

Slice 1 intentionally binds payload in governed invocation/record surfaces using:

- `opaque_payload.payload_handle`
- `opaque_payload.byte_length`
- `opaque_payload.transport`

It does not bind payload bytes or payload hashes into evaluator-facing structures. This preserves strict evaluator blindness while accepting weaker replay payload binding for the first implementation slice.
