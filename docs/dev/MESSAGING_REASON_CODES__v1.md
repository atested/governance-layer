# Messaging Reason Codes v1

## Objective

Define the bounded `RC-MSG-*` design set for the messaging proof surface only.

## Scope

These codes are limited to:

- messaging invocation structure
- canonical destination identity
- mapping/version linkage
- ALLOW/DENY-only proof-surface enforcement
- evaluator blindness guarantees

They do not cover message semantics or content governance.

## Proposed Reason Codes

| RC | Trigger | Notes |
|---|---|---|
| `RC-MSG-UNKNOWN-SURFACE-BINDING` | `surface_binding_id` not present in explicit messaging map | Fail closed; no provider inference |
| `RC-MSG-MAPPING-VERSION-MISMATCH` | request `mapping_version` does not match mapped entry | Versioned mapping must stay explicit |
| `RC-MSG-CAPABILITY-MAPPING-MISMATCH` | request capability class disagrees with mapped capability class | Prevents `MSG_SEND` / `MSG_REPLY` confusion |
| `RC-MSG-CANONICAL-DESTINATION-MISSING` | canonical destination object absent or malformed | Canonical destination is required |
| `RC-MSG-CANONICAL-DESTINATION-KIND-MISMATCH` | canonical destination kind disagrees with mapping entry | Prevents structural rerouting |
| `RC-MSG-DESTINATION-CLASS-DISALLOWED` | raw destination audit class is not allowed for the selected binding | Structural audit-input scoping only |
| `RC-MSG-DESTINATION-DISALLOWED` | canonical destination identity falls outside mapped destination scope | Canonical destination remains authoritative |
| `RC-MSG-RAW-DESTINATION-MISSING` | raw destination audit evidence absent | Audit evidence required even though it is not authoritative |
| `RC-MSG-OPAQUE-PAYLOAD-MISSING` | opaque payload handle metadata absent | Payload transport basis required |
| `RC-MSG-TRANSPORT-UNAUTHORIZED` | opaque payload transport kind is not allowed for the selected binding | Transport authorization is structural only |
| `RC-MSG-PAYLOAD-SIZE-EXCEEDED` | opaque payload byte length exceeds mapped maximum | No content inspection required |
| `RC-MSG-RATE-EXCEEDED` | structural rate-window count exceeds mapped maximum | Slice 1 uses bounded structural rate metadata, not global metering |
| `RC-MSG-CONTENT-FIELD-PRESENT` | evaluator-facing invocation includes content-bearing fields | Structural blindness enforcement |
| `RC-MSG-REPLY-CONTEXT-MISSING` | `MSG_REPLY` missing reply-context linkage | Reply target must be structurally explicit |
| `RC-MSG-REPLY-TARGET-MISMATCH` | reply-context identity inconsistent with canonical destination identity | Canonical reply identity must stay coherent |
| `RC-MSG-DECISION-ALPHABET-VIOLATION` | any non-`ALLOW`/`DENY` messaging decision attempted | Excludes `UNDECIDED` from this surface |
| `RC-MSG-MISSING-INTENT-FIELDS` | required messaging intent fields are absent | Mirrors existing governance intent requirement on the messaging surface |

## Deterministic Ordering Recommendation

Later implementation should use stable reason ordering for multi-reason DENY outcomes:

1. `RC-MSG-UNKNOWN-SURFACE-BINDING`
2. `RC-MSG-MAPPING-VERSION-MISMATCH`
3. `RC-MSG-CAPABILITY-MAPPING-MISMATCH`
4. `RC-MSG-CANONICAL-DESTINATION-MISSING`
5. `RC-MSG-CANONICAL-DESTINATION-KIND-MISMATCH`
6. `RC-MSG-DESTINATION-CLASS-DISALLOWED`
7. `RC-MSG-DESTINATION-DISALLOWED`
8. `RC-MSG-RAW-DESTINATION-MISSING`
9. `RC-MSG-OPAQUE-PAYLOAD-MISSING`
10. `RC-MSG-TRANSPORT-UNAUTHORIZED`
11. `RC-MSG-PAYLOAD-SIZE-EXCEEDED`
12. `RC-MSG-RATE-EXCEEDED`
13. `RC-MSG-REPLY-CONTEXT-MISSING`
14. `RC-MSG-REPLY-TARGET-MISMATCH`
15. `RC-MSG-CONTENT-FIELD-PRESENT`
16. `RC-MSG-DECISION-ALPHABET-VIOLATION`

## Explicit Exclusions

No messaging reason code should encode:

- body sentiment
- safe/unsafe content classes
- topic classification
- attachment meaning
- user intent semantics beyond required structural fields

Those would widen the surface into content governance, which is out of scope.

## TASK_399 Slice-1 Note

`RC-MSG-RATE-EXCEEDED` in this first slice is intentionally driven by bounded structural metadata (`audit_scope.rate_window_count`) rather than a broader global rate-metering subsystem. This keeps the messaging proof surface narrow while still wiring the operational reason code into the evaluator path.
