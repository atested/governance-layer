# TASK_399 Post-Implementation Review v1

## Objective

Review TASK_399, the first messaging proof-surface implementation slice, to determine whether its tranche-closure claim is justified exactly as implemented and whether the branch is safe to merge.

## Reviewed Claim

TASK_399 claims to implement a bounded first messaging proof-surface slice that:

- preserves the capability-invocation boundary as the primary governance boundary
- keeps ordinary user-visible text outside governance scope
- enforces `ALLOW` / `DENY` only
- preserves structural evaluator blindness to payload content
- makes canonical destination identity authoritative for evaluation and replay
- uses explicit, versioned, fail-closed mapping
- fully resolves Gap A
- resolves Gap B as Option 1 only

## Review Result

**Supported**

The branch implements the bounded first-slice claim honestly. The implementation is materially narrower than a full messaging system and does not overclaim content-governance or stronger payload-binding closure.

## Scope / Contract / Code Findings

### Messaging slice support

Supported.

The slice is present across:

- registry support in `capabilities/capability-registry.json`
- explicit versioned bindings in `capabilities/messaging-tool-map.v1.json`
- structural evaluator logic in `scripts/policy-eval.py`
- messaging helper support in `scripts/messaging_surface.py`
- replay binding in `scripts/replay-record.py`
- bounded post-ALLOW forwarding in `mcp/server.py`
- conformance coverage in `tests/test_msg_policy_surface.sh`
- forwarding/evaluation separation coverage in `system/tests/test_mcp_msg_surface.sh`

### Gap A review

Supported.

All six required additive operational codes exist and are wired in the evaluator path:

- `RC-MSG-MISSING-INTENT-FIELDS`
- `RC-MSG-DESTINATION-DISALLOWED`
- `RC-MSG-DESTINATION-CLASS-DISALLOWED`
- `RC-MSG-TRANSPORT-UNAUTHORIZED`
- `RC-MSG-PAYLOAD-SIZE-EXCEEDED`
- `RC-MSG-RATE-EXCEEDED`

The branch also wires the rest of the bounded `RC-MSG-*` set needed for the proof surface.

### Gap B review

Supported.

TASK_399 resolves Gap B as Option 1 only:

- governed/evaluator-facing structures bind opaque payload handle, byte length, and transport kind
- no payload bytes or payload hash are added to evaluator-facing schema, policy inputs, or decision-record extension fields
- the limitation is documented explicitly in the imported messaging design set after slice-1 updates

No hidden stronger payload-binding claim was found.

### Evaluator blindness review

Supported.

Evaluator-facing structures remain structurally blind:

- `scripts/policy-eval.py` rejects content-bearing fields through `contains_content_fields(...)`
- `tests/test_msg_policy_surface.sh` proves content indifference explicitly in `T-MSG-CONTENT-001`
- `T-MSG-CONTENT-003` proves denied content is not retained in the governed record
- decision-record docs and invocation-schema docs remain content-blind after the slice-1 updates

### ALLOW / DENY review

Supported.

Messaging evaluation is `ALLOW` / `DENY` only:

- evaluator policy inputs explicitly bind `decision_alphabet` to `["ALLOW", "DENY"]`
- the map file uses `["ALLOW", "DENY"]`
- `RC-MSG-DECISION-ALPHABET-VIOLATION` is present and covered

### Canonical destination authority review

Supported.

Canonical destination identity is authoritative in code and replay:

- evaluator policy inputs and normalized args bind canonical destination identity
- `tests/test_msg_policy_surface.sh` proves raw destination variation does not change evaluation when canonical destination is held constant
- replay compares `messaging_map_hash` and messaging normalized args, preserving canonical replay binding

### Mapping fail-closed review

Supported.

The implementation uses:

- explicit `surface_binding_id`
- explicit `mapping_version`
- explicit `messaging_map_hash`
- deny on unmapped / mismatched / invalid binding state

No provider inference or fallback aliasing was found.

## Imported Messaging Design-Doc Foundation Review

### Were the imported docs the correct settled foundation?

Yes.

The branch imported the messaging design docs from the exact settled commit identified in the earlier design tranche:

- `583a8d4f54a6117f13240e9cb1659c4905db4dbb`

This review found no evidence that the imported set came from an unrelated or stale source.

### Were the imported docs modified after import?

Yes, but only in bounded implementation-alignment ways.

Relative to the imported foundation, TASK_399 changes are limited to four messaging docs:

- `docs/dev/MESSAGING_DECISION_RECORD_EXTENSION__v1.md`
- `docs/dev/MESSAGING_INVOCATION_SCHEMA__v1.md`
- `docs/dev/MESSAGING_PROOF_SURFACE_IMPLEMENTATION_DESIGN__v1.md`
- `docs/dev/MESSAGING_REASON_CODES__v1.md`

Those changes:

- add the messaging-map replay binding note
- add the slice-1 payload-handle / byte-length / transport clarification
- add the Gap B Option 1 limitation note
- extend the reason-code design doc to match the actual wired operational set

These are implementation-alignment updates, not architectural rewrites.

### Did the imported docs introduce contradiction or stale-state risk?

No material contradiction found.

The imported foundation plus the four bounded updates stay internally consistent with the implementation. They do not reintroduce:

- content-governance semantics
- `UNDECIDED`
- generic proxy framing
- stronger payload-binding claims than were implemented

## Boundary Leakage Review

None material found.

The branch does not widen into:

- shell proof surface
- generic multi-surface proxying
- DLP
- content moderation
- semantic message evaluation
- forwarding-receipt payload-binding upgrade
- UNDECIDED / triage semantics

The post-ALLOW forwarder in `mcp/server.py` stays subordinate to the evaluation boundary and is limited to opaque payload transport after `ALLOW`.

## Canonical-Request Failure Review

The reported `tests/test_canonical_request.sh` failure is best classified as preexisting environment sensitivity, not a messaging regression.

Evidence:

- the failure occurs when `GOV_CANONICAL_REPO_PATH` / `GOV_RUNTIME_PATH` are unset and legacy registry placeholders remain unresolved
- the same test passes when those environment variables are set explicitly
- TASK_399 does not alter the filesystem allowlist semantics that drive that test

## Missing Evidence

No material missing evidence was found for the bounded slice claim.

The current messaging-specific tests are sufficient for:

- content indifference
- explicit content-field rejection
- canonical destination authority
- map fail-closed behavior
- reply-structure enforcement
- replay map-drift detection
- forwarding/evaluation separation

## Corrective Patch Requirement

No corrective patch required.

## Merge Judgment

**Merge-ready as-is**

TASK_399 is safe to merge as a bounded first messaging proof-surface slice. The claim is supported exactly as:

- first slice only
- Gap A fully wired
- Gap B Option 1 only
- structural content blindness preserved

It is not broad messaging completion, and the branch does not materially overclaim that it is.
