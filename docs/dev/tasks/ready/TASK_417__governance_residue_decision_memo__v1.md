# TASK_417 — governance residue decision memo v1

## 1. PURPOSE

Compare the three remaining governance-residue buckets that are no longer safely implementation-ready after `TASK_413`, `TASK_415`, and `TASK_416`, and state the exact product decision needed before bounded implementation can continue.

## 2. CURRENT_MAIN_BASELINE

- `TASK_413` consumed the first packaged slices in the three lanes under discussion:
  - external summary-contract parity residue audit
  - provider-evidence / receipt-linkage strengthening
  - Combo A structured summary emission
- `TASK_415` corrected GovCore planning/reference naming and did not reopen implementation residue.
- `TASK_416` correctly concluded that no follow-on implementation package was safe from current-main truth alone.
- Current-main truth relevant to this memo:
  - `proof_packet_verify_summary_v1` still emits `packet_hash` as a string
  - `validate_proof_bundle_summary_v1` still emits `packet_hash` as `{algo, value}`
  - messaging already has bounded rate-governance wiring and tests on main
  - `verify-chain.py --summary-json` already emits `chain_verification_summary_v1`, including completed terminal-process summary rows

## 3. RESIDUE_BUCKET_1_PACKET_HASH_NORMALIZATION

- `REMAINING_GAP`
  - The summary surfaces still diverge on `packet_hash` shape:
    - `proof_packet_verify_summary_v1` uses a string
    - `validate_proof_bundle_summary_v1` uses structured `{algo, value}`
- `WHY_NOT_READY`
  - This is concrete, but it is breaking-risk rather than merely underspecified.
  - Current main does not expose a migration stance, versioning stance, or compatibility rule for consumers of the proof-packet summary.
- `REQUIRED_DECISION`
  - Greg must decide whether consumer-facing summary contract consistency is important enough to justify a breaking or versioned normalization move.
  - Put differently: should the project accept contract churn now for consistency, or preserve the current split until a broader contract versioning move is chosen?
- `LATER_BOUNDING_CONDITION`
  - A bounded implementation tranche becomes safe only after one contract stance is chosen:
    - additive compatibility bridge
    - explicit version bump / schema split
    - or intentional deferral with the inconsistency frozen for now
- `STATUS: REFRAME_FIRST`

## 4. RESIDUE_BUCKET_2_MESSAGING_FOLLOW_ON

- `REMAINING_GAP`
  - Messaging still has nominal follow-on residue in three shapes:
    - structural rate-governance strengthening
    - post-ALLOW evidence-contract clarification
    - triage / non-resolution extension
- `WHY_NOT_READY`
  - The highest-ranked remaining implementation-looking slice, structural rate-governance strengthening, is no longer cleanly isolated:
    - current main already enforces `max_rate_window_count`
    - current main already emits and tests `RC-MSG-RATE-EXCEEDED`
    - what “extend beyond current reason-code usage” means is no longer explicit enough to dispatch implementation safely
  - The next clearest item, post-ALLOW evidence-contract clarification, is spec/docs work, not implementation.
  - The triage/non-resolution path is wider than the current messaging doctrine boundary.
- `REQUIRED_DECISION`
  - Greg must decide what exact additional operator or governance value is wanted from messaging beyond the landed provider-evidence slice.
  - The needed decision is not “implement messaging follow-on” generically; it is “choose the next tight messaging delta.”
- `LATER_BOUNDING_CONDITION`
  - A bounded tranche becomes safe only if the next delta is stated explicitly in one of these narrow forms:
    - stricter structural rate surface beyond the existing evaluator wiring
    - explicit post-ALLOW evidence contract surface to document/enforce
    - or an intentional doctrine expansion into non-ALLOW/DENY, which would need separate authorization
- `STATUS: REFRAME_FIRST`

## 5. RESIDUE_BUCKET_3_TERMINAL_PRESENTATION_OR_DOCTRINE

- `REMAINING_GAP`
  - The only live-looking post-selector residue after Combo A is terminal-presentation / doctrine coherence beyond the already-landed structured summary emission.
- `WHY_NOT_READY`
  - Current main already ships:
    - `verify-chain.py --summary-json`
    - `chain_verification_summary_v1`
    - terminal-process summary coverage in tests
  - What remains is not a clean runtime gap; it is a presentation/doctrine question about what further terminal coherence should mean after the summary artifact already exists.
  - That makes this bucket lower leverage than the other two and more vulnerable to dissolving into doctrine continuation.
- `REQUIRED_DECISION`
  - Greg must decide whether any additional terminal-presentation work is actually desired as product value, or whether Combo A is sufficient and the residue should stay deferred.
- `LATER_BOUNDING_CONDITION`
  - A later tranche is safe only if a missing operator-facing terminal presentation artifact or invariant is named concretely beyond the already-landed summary JSON.
- `STATUS: DEFER`

## 6. CROSS_BUCKET_COMPARISON

- Packet-hash normalization is the most concrete remaining gap.
  - Risk class: `breaking-risk`
  - It needs a contract stance decision, not more discovery.
- Messaging follow-on is the most obviously still-live lane.
  - Risk class: `non-breaking but underspecified`
  - It needs a tighter delta definition before implementation can resume.
- Terminal-presentation / doctrine residue is the least urgent.
  - Risk class: `doctrine/presentation-only`
  - Current main already covers the strongest runtime seam that used to justify it.

Net comparison:
- If Greg wants the fastest path back to implementation, packet-hash normalization is the sharpest decision point because the gap is real and local.
- If Greg wants to avoid contract risk and continue additive work, messaging needs a tighter delta definition first.
- The doctrine/presentation residue does not currently justify being first.

## 7. DECISION_REQUIRED_FROM_GREG

Greg only needs to make one primary decision now:

1. Decide whether to take an explicit contract stance on `packet_hash` normalization.

That decision then determines the next path:
- If `yes`, the project can bound the next tranche around the packet-hash contract move.
- If `no`, the next viable move is to define a tighter non-breaking messaging delta before implementation continues.

Secondary decision only if Greg declines the packet-hash move:
- choose whether messaging follow-on should target:
  - structural rate-governance extension, or
  - post-ALLOW evidence-contract clarification

No immediate decision is needed on doctrine residue unless Greg specifically wants more terminal presentation behavior beyond Combo A.

## 8. RECOMMENDED_NEXT_DECISION_PATH

`DECIDE_PACKET_HASH_STANCE`

Reason:
- it is the most concrete remaining gap
- the blocker is explicit and product-shaped
- a yes/no stance here cleanly separates “safe next implementation tranche” from “return to messaging reframing”
- the other two buckets either need tighter problem definition first or are best deferred
