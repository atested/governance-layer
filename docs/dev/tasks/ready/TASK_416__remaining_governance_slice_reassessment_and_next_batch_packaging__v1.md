# TASK_416 — remaining governance slice reassessment and next batch packaging v1

## 1. PURPOSE

Reassess the remaining bounded residue from the packaged messaging, external validator/operator hardening, and post-selector RDD lanes after `TASK_413` and `TASK_415`, then determine whether current-main truth still supports packaging a direct next implementation batch.

## 2. CURRENT_MAIN_RESIDUE

- `TASK_413` consumed the first packaged slice in each of the three lanes under review:
  - external summary-contract parity residue audit
  - provider-evidence / receipt-linkage strengthening
  - Combo A structured summary emission
- `TASK_415` did not change these implementation surfaces; it corrected planning/reference naming only.
- Current-main residue after those landings:
  - messaging:
    - structural rate-governance strengthening
    - post-ALLOW evidence-contract clarification
    - triage / non-resolution extension
  - external validator/operator hardening:
    - `packet_hash` field-shape inconsistency between `proof_packet_verify_summary_v1` and `validate_proof_bundle_summary_v1`
    - broader export-contract convergence residue
  - post-selector RDD:
    - chain verification terminal-presentation coherence
    - broader deferred doctrine continuation remains out of scope

## 3. CANDIDATES_REASSESSED

### Messaging follow-on residue
- `Slice A` is consumed by `TASK_413`.
- `Slice B` does not remain cleanly implementation-ready:
  - current main already carries bounded structural rate wiring in `scripts/policy-eval.py`
  - `max_rate_window_count` exists in `capabilities/messaging-tool-map.v1.json`
  - `RC-MSG-RATE-EXCEEDED` is already exercised in `tests/test_msg_policy_surface.sh`
  - what remains of “extend beyond current reason-code usage” is not isolated clearly enough to package as one claim-safe implementation slice
- `Slice C` is explicitly a documentation/spec clarification lane, not an implementation slice.
- `Slice D` remains broader and doctrinally wider than an immediate bounded next slice.

### External validator/operator hardening residue
- The parity audit slice is consumed by `TASK_413`.
- The strongest concrete residue is still `packet_hash` shape normalization.
- That residue is still a breaking-change-risk surface:
  - `proof_packet_verify_summary_v1` uses a string form
  - `validate_proof_bundle_summary_v1` uses `{algo, value}`
  - current-main evidence still does not provide a migration/contract stance that makes the implementation slice low-risk

### Post-selector RDD residue
- Combo A structured summary emission is consumed by `TASK_413`.
- The remaining shortlisted seam, chain verification terminal-presentation coherence, is not cleanly implementation-ready from current-main truth:
  - `scripts/verify-chain.py --summary-json` already emits `chain_verification_summary_v1`
  - `tests/test_verify_chain_summary_json.sh` and `tests/test_rdd_terminal_judgment.sh` already cover terminal-process summary output
  - the remaining gap is still described by the canon as a doctrine/presentation coherence seam, not a clearly isolated runtime tranche

## 4. PRIMARY_NEXT_SLICE

`NONE`

No remaining slice is both clearly unconsumed and cleanly bounded enough to package as the next implementation tranche from current-main truth alone.

## 5. SECONDARY_BATCHABLE_SLICE

`NONE`

No secondary slice is safely batchable because:
- the messaging residue is partially realized and under-specified as an implementation gap,
- the external validator residue is concrete but breaking-risk,
- the remaining post-selector seam is still better described as doctrine/spec residue than direct implementation work.

## 6. PACKAGING_DECISION

`NO_SAFE_PACKAGE`

No `TASK_416A` or `TASK_416B` follow-on implementation specs should be created from this reassessment pass.

## 7. WHY_NOT_THE_OTHERS

- Do not package messaging structural rate-governance strengthening as a next implementation slice:
  - the foundational rate-governance wiring already exists on main
  - the remaining delta is not sharply enough defined to dispatch claim-safely
- Do not package `packet_hash` shape normalization next:
  - it is still the clearest external residue item
  - but it remains a breaking-risk contract change without a current-main migration stance
- Do not package post-selector terminal-presentation coherence as an implementation slice:
  - current main already ships structured chain summary emission
  - what remains is still framed as coherence/doctrine shaping rather than a discrete runtime closure step

## 8. BOUNDS_AND_INVARIANTS

- Use current-main truth only.
- Do not repackage anything already completed by `TASK_413` or `TASK_415`.
- Prefer additive, non-breaking slices; if the remaining residue is breaking-risk or under-specified, do not force an implementation batch.
- Do not create follow-on specs unless the slice is bounded enough to dispatch directly.
- Do not broaden messaging into triage/non-resolution redesign.
- Do not broaden external residue into proof/export redesign.
- Do not broaden post-selector residue into doctrine continuation or multi-case expansion.
