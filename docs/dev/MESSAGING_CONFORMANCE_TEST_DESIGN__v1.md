# Messaging Conformance Test Design v1

## Objective

Define the bounded conformance test design for the messaging proof surface only, with emphasis on content indifference and structural invariants.

## Coverage Targets

The later implementation should prove:

- evaluator blindness to content
- canonical destination authority
- raw destination audit preservation
- explicit versioned mapping fail-closed behavior
- ALLOW/DENY-only decision alphabet
- evaluation/forwarding phase separation

## Invariant Coverage Map

| INV | Test focus |
|---|---|
| `INV-M2` | evaluator rejects content-bearing fields; payload remains opaque |
| `INV-M3` | canonical destination drives decision/replay; raw destination is audit-only |
| `INV-M4` | no `UNDECIDED` or other third decision state for messaging |
| `INV-M5` | forwarding cannot proceed without prior ALLOW and matching decision linkage |
| `INV-M6` | mapping/version mismatch denies fail-closed |

## Test Matrix

### Content indifference

1. `T-MSG-CONTENT-001`
   - same structural request, different payload bytes behind same handle class
   - expected: same evaluator decision
2. `T-MSG-CONTENT-002`
   - evaluator-facing request includes forbidden `body` field
   - expected: `DENY` + `RC-MSG-CONTENT-FIELD-PRESENT`
3. `T-MSG-CONTENT-003`
   - evaluator-facing request includes forbidden `subject` field
   - expected: `DENY` + `RC-MSG-CONTENT-FIELD-PRESENT`

### Canonical destination authority

4. `T-MSG-DEST-001`
   - canonical destination valid, raw destination alias differs
   - expected: evaluation uses canonical destination, raw preserved only for audit
5. `T-MSG-DEST-002`
   - canonical destination missing
   - expected: `DENY` + `RC-MSG-CANONICAL-DESTINATION-MISSING`
6. `T-MSG-DEST-003`
   - canonical destination kind mismatches mapped kind
   - expected: `DENY` + `RC-MSG-CANONICAL-DESTINATION-KIND-MISMATCH`

### Mapping fail-closed behavior

7. `T-MSG-MAP-001`
   - unknown `surface_binding_id`
   - expected: `DENY` + `RC-MSG-UNKNOWN-SURFACE-BINDING`
8. `T-MSG-MAP-002`
   - wrong `mapping_version`
   - expected: `DENY` + `RC-MSG-MAPPING-VERSION-MISMATCH`
9. `T-MSG-MAP-003`
   - `MSG_SEND` request against `MSG_REPLY` mapping
   - expected: `DENY` + `RC-MSG-CAPABILITY-MAPPING-MISMATCH`

### Reply-specific structure

10. `T-MSG-REPLY-001`
    - `MSG_REPLY` missing `reply_context`
    - expected: `DENY` + `RC-MSG-REPLY-CONTEXT-MISSING`
11. `T-MSG-REPLY-002`
    - `reply_context.reply_target_id` differs from canonical destination id
    - expected: `DENY` + `RC-MSG-REPLY-TARGET-MISMATCH`

### Decision alphabet

12. `T-MSG-DECISION-001`
    - attempt to emit `UNDECIDED`
    - expected: fail-closed / schema rejection / `RC-MSG-DECISION-ALPHABET-VIOLATION`

### Forwarding phase separation

13. `T-MSG-FWD-001`
    - forwarding attempted after `DENY`
    - expected: blocked
14. `T-MSG-FWD-002`
    - forwarding attempted with canonical destination different from decision record
    - expected: blocked
15. `T-MSG-FWD-003`
    - forwarding attempted with same ALLOW decision and same canonical destination
    - expected: allowed to proceed
16. `T-MSG-FWD-004`
    - forwarding receipt emitted after `ALLOW`
    - expected: receipt binds record hash, canonical destination, payload handle, byte length, and forwarded payload digest
17. `T-MSG-REPLAY-003`
    - payload bytes behind the same opaque handle mutate after `ALLOW`
    - expected: evaluator replay invariants remain stable, but replay fails against forwarding receipt payload digest

## False-Closure Cases

The surface is not closed if:

- payload content is simply ignored by convention but still accepted in evaluator-facing schemas
- raw destination input can override canonical destination identity
- mappings are inferred from provider names rather than explicitly declared
- the proxy can forward after `DENY`
- payload digest appears in evaluator-facing request or decision-record structures
- replay ignores forwarding receipt drift when a receipt exists
- `UNDECIDED` remains reachable on messaging decisions

## Fixture Design Recommendation

Later tests should use fixtures under:

- `tests/fixtures/messaging/`

Fixture classes:

- `msg_send_slack_like_allow.json`
- `msg_send_unknown_binding.json`
- `msg_send_content_field_present.json`
- `msg_reply_email_like_allow.json`
- `msg_reply_missing_context.json`
- `msg_reply_target_mismatch.json`

The payload itself should live outside evaluator fixtures and be referenced only by opaque handle.

## Acceptance Summary

The messaging proof surface should count as conformant only when:

1. all content-indifference tests pass
2. all mapping fail-closed tests pass
3. all canonical-destination replay tests pass
4. all reply-structure tests pass
5. forwarding phase separation is proven with explicit blocked and allowed paths
6. post-ALLOW forwarding receipts prove stronger payload replay binding without widening evaluator-visible structures
