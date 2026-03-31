# Messaging Proxy Lifecycle v1

## Objective

Describe the bounded proxy lifecycle for the messaging proof surface only.

## Lifecycle Summary

The messaging proxy is a subordinate forwarding surface. It is not the primary governance boundary.

## Phase 1: Invocation Construction

Caller constructs a governed invocation for:

- `MSG_SEND`
- `MSG_REPLY`

Required inputs to the evaluator:

- `surface_binding_id`
- `mapping_version`
- canonical destination identity
- raw destination input for audit
- opaque payload handle metadata
- structural intent
- reply context for `MSG_REPLY`

Payload bytes are not provided to the evaluator.

## Phase 2: Evaluation

Evaluator:

- loads explicit versioned messaging map
- validates capability-class to binding compatibility
- validates canonical destination structure
- validates reply-context linkage for `MSG_REPLY`
- validates absence of content-bearing fields
- emits `ALLOW` or `DENY`

Evaluator does not:

- inspect message content
- inspect attachments semantically
- perform content safety scoring
- emit `UNDECIDED`

## Phase 3: Decision Record Emission

The evaluator emits a decision record containing:

- canonical destination identity
- raw destination audit evidence
- mapping linkage
- opaque payload-handle presence metadata
- `ALLOW` or `DENY`

## Phase 4: Forwarding Gate

Proxy may proceed only when:

- decision is `ALLOW`
- surface binding matches the decision record
- canonical destination identity matches the decision record
- payload handle is resolvable

Any mismatch fails closed.

## Phase 5: Opaque Payload Retrieval

Only after `ALLOW`, the proxy may fetch payload bytes from the opaque payload handle.

The payload is transported as opaque material. The proxy may need provider-specific framing to deliver bytes, but that does not alter governance scope.

## Phase 6: Provider Forwarding

Proxy forwards to the mapped provider operation using:

- the explicit mapping entry
- the authoritative canonical destination identity
- the opaque payload bytes

No provider fallback or alias inference is allowed.

## Phase 7: Forwarding Receipt

TASK_400 adds a bounded forwarding receipt linked to:

- decision record hash
- request id
- surface binding id
- canonical destination id
- opaque payload handle
- opaque payload byte length
- payload digest for the bytes actually forwarded

This receipt is subordinate to the evaluation record and exists only in the forwarding-phase evidence layer.

The receipt must not widen evaluator-facing structures:

- payload digest must not enter `policy_inputs`
- payload digest must not enter `normalized_args`
- payload digest must not enter other evaluator-facing messaging request fields

## Lifecycle Failure Modes

The proxy must fail closed if:

- mapping entry missing
- decision is `DENY`
- canonical destination mismatch between evaluation and forwarding
- reply target mismatch for `MSG_REPLY`
- payload handle missing or unreadable

## What This Lifecycle Excludes

This lifecycle does not include:

- generic proxy infrastructure for unrelated governed surfaces
- content inspection before forwarding
- shell/web surface governance
- DLP or content moderation
- triage or `UNDECIDED`
