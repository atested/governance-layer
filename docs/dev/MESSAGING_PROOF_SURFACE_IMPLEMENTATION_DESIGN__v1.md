# Messaging Proof Surface Implementation Design v1

## Status

Design only. No runtime implementation is created by this artifact set.

## Objective

Translate the validated Messaging Proof Surface architecture into repo-ready implementation-design materials for a later bounded implementation pass, while preserving the approved architectural boundaries:

- governance applies to privileged capability invocation
- the primary boundary is capability invocation, not ordinary text
- the governed object is invocation of a governed messaging capability surface
- ordinary user-visible text remains inert output and outside governance scope
- operative promotion is subordinate to the primary boundary
- messaging proof surface uses `ALLOW` / `DENY` only
- evaluator is blind to payload content
- proxy may transport payload bytes post-decision only as opaque transport material
- canonical destination identity is authoritative for evaluation and replay
- raw destination input is preserved only as audit evidence
- intent remains structural and audit-oriented, not content-semantic
- content governance is out of scope

## Recommended Artifact Set

The later implementation should be driven by the following design artifacts:

1. `docs/dev/MESSAGING_PROOF_SURFACE_IMPLEMENTATION_DESIGN__v1.md`
2. `docs/dev/MESSAGING_CAPABILITY_REGISTRY_AND_MAPPING_SCHEMA__v1.md`
3. `docs/dev/MESSAGING_INVOCATION_SCHEMA__v1.md`
4. `docs/dev/MESSAGING_DECISION_RECORD_EXTENSION__v1.md`
5. `docs/dev/MESSAGING_REASON_CODES__v1.md`
6. `docs/dev/MESSAGING_CONFORMANCE_TEST_DESIGN__v1.md`
7. `docs/dev/MESSAGING_PROXY_LIFECYCLE__v1.md`

These are intentionally placed under `docs/dev/` because current repo patterns keep pre-implementation contract material there, while runtime contracts remain in `docs/` only after implementation and externalization.

## Minimal Future File / Package Recommendation

This is a recommendation only. It does not create runtime files.

### Design-phase locations

- `docs/dev/MESSAGING_*`

### Future implementation-phase locations

- `capabilities/capability-registry.json`
  - additive entries for `MSG_SEND` and `MSG_REPLY`
- `capabilities/messaging-tool-map.v1.json`
  - explicit external-tool binding map for messaging proof surface only
- `tests/fixtures/messaging/`
  - evaluator fixtures without content-bearing payload fields
- `tests/test_msg_*`
  - bounded messaging conformance tests
- optional future runtime helper surfaces
  - `scripts/` or `mcp/` only if later implementation chooses governed proxy wiring

This recommendation stays narrow and does not imply shell, web, generic proxying, DLP, or content governance work.

## Surface Boundary

### Governed boundary

The governed boundary is the privileged invocation of:

- `MSG_SEND`
- `MSG_REPLY`

The evaluator governs the right to invoke those capability surfaces against an authoritative canonical destination identity.

### Non-governed boundary

The following are outside governance scope for this proof surface:

- the semantic meaning of message body text
- subject/body interpretation
- attachment semantics
- content moderation
- downstream recipient interpretation
- freeform message text shown to users

### Evaluation phase vs forwarding phase

The design preserves a hard split:

1. **Evaluation phase**
   - receives only structural invocation metadata
   - evaluates canonical destination identity, explicit mapping, action type, and bounded audit fields
   - never receives content-bearing payload fields
2. **Forwarding phase**
   - may fetch and transport payload bytes only after `ALLOW`
   - treats payload as opaque transport material
   - must not reinterpret governance scope as content governance

This split is constitutive, not advisory.

## Messaging Invariants

### INV-M1

Governance attaches to privileged messaging capability invocation, not to ordinary message text.

### INV-M2

Evaluator-facing messaging invocation objects must contain no content-bearing payload fields. Payload may be represented only by opaque transport metadata such as handle presence and bounded byte count.

### INV-M3

Canonical destination identity is the sole authoritative destination identity for evaluation and replay. Raw destination input is preserved only as audit evidence and must not override canonical identity.

### INV-M4

The messaging proof surface decision alphabet is `ALLOW` or `DENY` only. `UNDECIDED` is excluded from this surface.

### INV-M5

Evaluation and forwarding are separate phases. Forwarding may occur only after an `ALLOW` decision and only against the same surface binding and canonical destination identity captured by the decision record.

### INV-M6

External-tool mapping must be explicit, versioned, and fail-closed. Missing, ambiguous, stale, or mismatched mappings must deny invocation rather than fall back to inference.

## Design Decisions

### Decision 1: Content blindness is structural

The evaluator-facing schema excludes fields such as:

- `message_text`
- `body`
- `subject`
- `html`
- `attachment_bytes`
- `attachment_names`

Later implementation should reject evaluator requests that attempt to smuggle such fields into governed invocation args.

### Decision 2: Intent remains structural

Intent stays audit-oriented and structurally scoped:

- why the privileged send/reply is being invoked
- expected output class
- constraints or audit tags

Intent is not a place for content policy or semantic analysis.

### Decision 3: Canonical destination is replay anchor

Replay and audit must bind to:

- `canonical_destination.kind`
- `canonical_destination.id`
- `surface_binding_id`
- `mapping_version`

Raw destination input may be stored for audit but cannot drive replay outcome.

### Decision 4: Proxy remains subordinate

The proxy is not the primary governance boundary. It is a post-decision forwarder subordinate to the capability invocation boundary.

### Decision 5: TASK_399 adopts Gap B Option 1

The first implementation slice binds payload only through:

- opaque payload handle
- opaque payload byte length
- opaque payload transport kind

It deliberately does **not** bind payload bytes or payload hashes into evaluator-facing structures. This is an explicit slice-1 limitation, not an accidental omission.

## Later Implementation Closure Criteria

The later implementation pass should count as architecturally closed for this proof surface only if it:

1. adds `MSG_SEND` and `MSG_REPLY` capability registration in fail-closed form
2. introduces explicit messaging external-tool mapping declarations
3. implements evaluator-facing invocation schemas with no content-bearing fields
4. records messaging decisions with canonical destination identity and raw-input audit evidence
5. enforces `ALLOW` / `DENY` only
6. proves content indifference and evaluation/forwarding phase separation with dedicated tests

## TASK_399 / TASK_400 Implementation Note

TASK_399 implements the first messaging proof-surface slice with:

- full bounded `RC-MSG-*` evaluator wiring, including the six previously missing operational codes
- explicit messaging map hash binding for replay
- strict ALLOW/DENY-only behavior
- structural content blindness
- a bounded post-ALLOW forwarder that consumes opaque payload handles only after `ALLOW`

TASK_400 strengthens replay binding without reopening the evaluator contract:

- post-ALLOW forwarding now emits a bounded forwarding receipt
- the forwarding receipt binds the payload actually forwarded through payload digest plus byte length
- replay may use that forwarding receipt to detect payload drift behind the same opaque handle
- payload digest remains outside evaluator-facing structures and decision inputs

The messaging proof surface still does not implement global rate-metering infrastructure or content evaluation.

## Explicit Exclusions

This design set does not authorize or imply:

- shell execution governance
- web request governance
- generic multi-surface proxy infrastructure
- DLP
- content moderation
- semantic checks on message content
- UNDECIDED or triage semantics for messaging
- broader MCP generalization

## Bounded Open Questions

None are architecturally blocking for the proof surface.

Later implementation may choose exact runtime file names for payload-handle storage or proxy adapter placement, but those are subordinate engineering choices as long as this design set remains intact.
