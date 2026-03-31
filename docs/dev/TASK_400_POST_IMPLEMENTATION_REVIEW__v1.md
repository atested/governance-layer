# TASK_400 Post-Implementation Review v1

## Objective

Review TASK_400, the messaging replay-strengthening second slice, to determine whether its tranche-closure claim is justified exactly as implemented and whether the branch is safe to merge.

## Reviewed Tranche-Closure Claim

TASK_400 claims to implement a bounded messaging proof-surface follow-on that:

- strengthens replay payload binding beyond TASK_399 Option 1
- keeps the stronger binding only in post-`ALLOW` forwarding evidence
- preserves evaluator blindness and the no-content decision-record rule
- preserves canonical destination authority, explicit map binding, and `ALLOW` / `DENY` only behavior

## Review Result

Claim status: `supported`

The branch implements the bounded TASK_400 claim honestly. The implementation materially strengthens replay binding while remaining narrower than delivery-confirmation semantics or broader proxy architecture.

## What Was Reviewed

Primary code surfaces:

- `scripts/messaging_surface.py`
- `scripts/replay-record.py`
- `mcp/server.py`

Primary test surfaces:

- `tests/test_msg_policy_surface.sh`
- `system/tests/test_mcp_msg_surface.sh`
- `system/tests/test_mcp_msg_replay_receipt.sh`
- `tests/test_replay.sh`

Primary doc surfaces:

- `docs/dev/MESSAGING_CONFORMANCE_TEST_DESIGN__v1.md`
- `docs/dev/MESSAGING_DECISION_RECORD_EXTENSION__v1.md`
- `docs/dev/MESSAGING_PROOF_SURFACE_IMPLEMENTATION_DESIGN__v1.md`
- `docs/dev/MESSAGING_PROXY_LIFECYCLE__v1.md`

## Support for the Claimed TASK_400 Closure

### Stronger replay binding exists

The branch adds a bounded post-`ALLOW` forwarding receipt at:

- `out/messaging_proxy/<request_id>/forward_receipt.json`

That receipt binds:

- `record_hash`
- `request_id`
- `surface_binding_id`
- canonical destination
- `payload_handle`
- `payload_transport`
- `payload_byte_length`
- `payload_sha256`

This is materially stronger than TASK_399 Option 1, which bound only opaque handle plus byte length.

### Stronger binding is confined to forwarding evidence

The stronger payload digest is written only by the post-`ALLOW` forwarder in `mcp/server.py`.

It is not added to:

- evaluator request args
- `policy_inputs`
- `normalized_args`
- messaging decision-record extension fields

This preserves the settled evaluator/evidence split.

### Replay is genuinely stronger than TASK_399 Option 1

`scripts/replay-record.py` now:

1. replays the original evaluator request as before
2. verifies baseline deterministic invariants
3. for messaging `ALLOW` records with a forwarding receipt present, verifies the receipt against:
   - decision-record linkage
   - canonical destination
   - opaque payload handle metadata
   - current bytes behind the opaque payload handle

The new `system/tests/test_mcp_msg_replay_receipt.sh` proves same-length payload drift is detected through:

- `forward_receipt.payload_sha256`

That is the key TASK_400 step-up over slice 1.

## Evaluator Blindness Check

Evaluator blindness remains structural, not advisory.

Confirmed in code:

- `scripts/policy-eval.py` still consumes only:
  - canonical destination
  - raw destination audit evidence
  - opaque payload handle
  - opaque payload transport
  - opaque payload byte length
- no payload bytes are passed to the evaluator
- no payload digest is passed to the evaluator
- content-bearing evaluator fields are still denied fail-closed

Confirmed in tests:

- `tests/test_msg_policy_surface.sh` still proves content indifference
- `tests/test_msg_policy_surface.sh` explicitly checks that neither `payload_hash` nor `payload_sha256` appears in the decision record
- `system/tests/test_mcp_msg_surface.sh` explicitly checks that `payload_sha256` remains absent from the decision record

## Preserved Messaging Invariants

The branch preserves all settled messaging invariants relevant to TASK_400:

- governed object remains privileged capability invocation
- messaging remains `ALLOW` / `DENY` only
- evaluator-facing structures remain content-blind
- forwarding phase remains distinct from evaluation phase
- canonical destination remains authoritative for evaluation and replay linkage
- mapping remains explicit, versioned, and fail-closed
- no semantic or content checks on payload were introduced

## Scope / Contract / Code Mismatches

No material scope, contract, or code mismatches were found.

The implementation matches the bounded TASK_400 claim:

- stronger replay binding is added
- the addition lives only in forwarding-phase evidence
- evaluator-facing messaging structures stay unchanged in their blindness properties

## Hidden Widening / Boundary Leakage

No material boundary leakage was found.

Specifically absent:

- delivery acknowledgement semantics
- provider-confirmed receipt semantics
- content governance or moderation
- DLP
- shell or generic multi-surface proxy work
- `UNDECIDED` / triage behavior

The new receipt is a local post-`ALLOW` forwarding artifact only. It does not overclaim provider delivery.

## Missing Evidence

No material missing evidence remains for the bounded slice claim.

The existing and added tests cover:

- evaluator blindness
- no-digest-in-record behavior
- `ALLOW`/`DENY`-only preservation
- forwarding receipt emission
- same-length payload drift detection through strengthened replay
- no-forward-after-`DENY`

## Merge Readiness

TASK_400 is safe to merge as-is.

It should be described narrowly as:

- bounded messaging replay strengthening via post-`ALLOW` forwarding receipt evidence

It should not be described as:

- provider-confirmed delivery
- full messaging delivery assurance
- broader messaging completion

## Corrective Patch Requirement

No corrective patch is required before merge.
