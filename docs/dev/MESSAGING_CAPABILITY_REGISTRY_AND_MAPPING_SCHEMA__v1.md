# Messaging Capability Registry And Mapping Schema v1

## Objective

Define a repo-ready additive extension shape for messaging proof-surface capability registration and external-tool mapping declarations, without editing runtime registry files yet.

## Registry Extension Recommendation

Future runtime registration should be additive inside `capabilities/capability-registry.json`.

### Proposed capability entries

```json
{
  "tool": "MSG_SEND",
  "capability_class": "MSG_SEND",
  "risk_level": "HIGH",
  "args": {
    "required": [
      "surface_binding_id",
      "mapping_version",
      "canonical_destination",
      "raw_destination_input",
      "opaque_payload",
      "intent"
    ],
    "optional": [
      "audit_scope"
    ]
  },
  "caps": {
    "decision_alphabet": [
      "ALLOW",
      "DENY"
    ],
    "content_visible_to_evaluator": false,
    "canonical_destination_required": true,
    "raw_destination_audit_required": true,
    "opaque_payload_required": true,
    "reply_context_required": false
  }
}
```

```json
{
  "tool": "MSG_REPLY",
  "capability_class": "MSG_REPLY",
  "risk_level": "HIGH",
  "args": {
    "required": [
      "surface_binding_id",
      "mapping_version",
      "canonical_destination",
      "raw_destination_input",
      "opaque_payload",
      "reply_context",
      "intent"
    ],
    "optional": [
      "audit_scope"
    ]
  },
  "caps": {
    "decision_alphabet": [
      "ALLOW",
      "DENY"
    ],
    "content_visible_to_evaluator": false,
    "canonical_destination_required": true,
    "raw_destination_audit_required": true,
    "opaque_payload_required": true,
    "reply_context_required": true
  }
}
```

## Mapping File Recommendation

Future explicit mapping declarations should live in a dedicated versioned file:

- `capabilities/messaging-tool-map.v1.json`

This keeps external-tool binding separate from the generic capability registry while still binding the two at evaluation time.

## Mapping Schema

### Top-level fields

- `mapping_schema_version`
  - string
  - required
  - example: `"messaging_tool_map.v1"`
- `entries`
  - array
  - required
  - each item defines one explicit governed binding

### Entry fields

- `mapping_id`
  - string
  - unique stable identifier for the binding entry
- `mapping_version`
  - string
  - required
  - additive-compatible only inside the same major version
- `capability_class`
  - enum
  - `MSG_SEND` or `MSG_REPLY`
- `surface_binding_id`
  - string
  - authoritative binding name referenced by invocation objects
- `provider`
  - string
  - bounded provider label such as `slack` or `smtp_email`
- `external_operation`
  - string
  - explicit provider operation name, not inferred at runtime
- `canonical_destination_kind`
  - string
  - destination identity class the evaluator expects
- `forwarder_contract_version`
  - string
  - version for post-decision forwarding contract
- `evaluator_contract_version`
  - string
  - version for evaluator-facing invocation contract
- `allowed_decisions`
  - array
  - must equal `["ALLOW", "DENY"]`
- `content_visible_to_evaluator`
  - boolean
  - must equal `false`
- `required_fields`
  - array of strings
  - enumerates mandatory invocation fields for the binding
- `fail_closed_on_mapping_miss`
  - boolean
  - must equal `true`

## Example Mapping Entries

These are design examples only.

### Slack-like send example

```json
{
  "mapping_id": "msg.slack.chat_post_message",
  "mapping_version": "1",
  "capability_class": "MSG_SEND",
  "surface_binding_id": "msg.slack.chat.postMessage.v1",
  "provider": "slack",
  "external_operation": "chat.postMessage",
  "canonical_destination_kind": "slack_channel",
  "forwarder_contract_version": "msg_forward.v1",
  "evaluator_contract_version": "msg_eval.v1",
  "allowed_decisions": ["ALLOW", "DENY"],
  "content_visible_to_evaluator": false,
  "required_fields": [
    "canonical_destination",
    "raw_destination_input",
    "opaque_payload",
    "intent"
  ],
  "fail_closed_on_mapping_miss": true
}
```

### Email-like reply example

```json
{
  "mapping_id": "msg.smtp.reply_to_message",
  "mapping_version": "1",
  "capability_class": "MSG_REPLY",
  "surface_binding_id": "msg.smtp.reply.v1",
  "provider": "smtp_email",
  "external_operation": "reply",
  "canonical_destination_kind": "email_reply_target",
  "forwarder_contract_version": "msg_forward.v1",
  "evaluator_contract_version": "msg_eval.v1",
  "allowed_decisions": ["ALLOW", "DENY"],
  "content_visible_to_evaluator": false,
  "required_fields": [
    "canonical_destination",
    "raw_destination_input",
    "opaque_payload",
    "reply_context",
    "intent"
  ],
  "fail_closed_on_mapping_miss": true
}
```

## Fail-Closed Rules

The later implementation should deny when:

- `surface_binding_id` is missing from the mapping file
- `mapping_version` does not match the declared entry
- `capability_class` and mapping entry disagree
- `canonical_destination.kind` does not match the mapped destination kind
- `content_visible_to_evaluator` is not `false`
- required invocation fields are absent

No provider inference, fuzzy matching, or fallback aliasing is permitted.

## Explicit Non-Fields

The mapping schema must not define evaluator-facing content fields such as:

- body text
- subject
- rendered HTML
- attachment names or bytes
- semantic labels derived from content

## Recommended Skeleton For Later Runtime JSON

```json
{
  "mapping_schema_version": "messaging_tool_map.v1",
  "entries": [
    {}
  ]
}
```
