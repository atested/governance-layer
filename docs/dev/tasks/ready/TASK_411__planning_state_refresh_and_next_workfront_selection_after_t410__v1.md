# TASK_411 — planning state refresh and next workfront selection after T410 v1

## 1. PURPOSE

Refresh current-main planning truth so it no longer treats replay-outcome governance-evidence propagation as an open next tranche, then determine whether refreshed current-main evidence supports a single next bounded governance workfront.

## 2. PHASE_1_CURRENT_MAIN_EVIDENCE

- `scripts/proof-packet.py` already emits `governance_evidence.replay_outcome` with `pass` / `fail` / `unavailable` semantics.
- `system/scripts/validate-proof-bundle.sh` already propagates `governance_evidence` into `validate_proof_bundle_summary_v1` and normalizes missing or invalid replay outcomes to `unavailable`.
- `tests/test_proof_packet_summary_json.sh` already covers:
  - pass replay outcome
  - fail replay outcome
  - unavailable replay outcome
- `tests/test_validate_proof_bundle_summary_json.sh` already covers:
  - propagated replay outcome on pass
  - propagated replay outcome on fail
  - normalization to unavailable
- `TASK_410` correctly records that the narrow replay-outcome propagation tranche is already landed on current main and is `SPEC_ONLY`.
- The following planning surfaces lagged on this exact point before refresh:
  - `CURRENT_MAIN_CAPABILITY_MAP.md`
  - `WORK_QUEUE.md` control-plane note
  - `POST_REFRESH_NEXT_WORKFRONT_CONFIRMATION__v1.md`
  - `RECORD_TO_PACKET_NEXT_TRANCHE_CONFIRMATION__v1.md`
- `TASK_409` was named as a Phase 1 required read in the dispatch, but no such file exists on current main. Phase 1 therefore used current-main reachable evidence plus the landed `TASK_410` artifact instead.

## 3. PHASE_1_REFRESH_ACTIONS

- Updated `CURRENT_MAIN_CAPABILITY_MAP.md` to:
  - baseline `origin/main @ 42d29911b855d5102bf0e3f19449c6c2588822e7`
  - remove replay-outcome propagation as an open preferred candidate
  - record that no single immediate formulation winner remains confirmed after replay-outcome tranche verification
- Updated `WORK_QUEUE.md` control-plane note to stop presenting post-traceability replay-outcome work as the current immediate winner.
- Updated `POST_REFRESH_NEXT_WORKFRONT_CONFIRMATION__v1.md` so it no longer recommends the already-landed replay-outcome slice as the next control step.
- Updated `RECORD_TO_PACKET_NEXT_TRANCHE_CONFIRMATION__v1.md` so it treats replay-outcome propagation as consumed baseline rather than an open next tranche.

## 4. PHASE_1_POST_REFRESH_STATE

- Refreshed planning state is coherent enough for selection.
- `CURRENT_MAIN_CAPABILITY_MAP.md` and `WORK_QUEUE.md` now agree on the key point needed for this decision:
  - current main remains in `NEXT_WORKFRONT_FORMULATION`
  - replay-outcome governance-evidence propagation is not an open next tranche
  - no single immediate formulation winner remains confirmed from current-main truth alone
- No material divergence remains on the exact T410 point.

## 5. CANDIDATES_CONSIDERED

### Candidate A — GovCore naming / boundary correction
- Not strong enough on current main.
- The boundary/naming ambiguity is real, but current main does not show it as the highest-leverage next bounded governance move.
- No landed current-main planning artifact cleanly upgrades it above the other remaining directions.

### Candidate B — AAT / Foundation v0 admissibility convergence
- Weakened below selection threshold.
- Older planning surfaces ranked it highly, but current-main `AAT_FOUNDATION_V0_CONVERGENCE_SPEC__v1.md` concludes the lane is not boundable as a strategic next direction.
- Selecting it now would ignore stronger current-main truth.

### Candidate C — Post-selector RDD continuation
- Real but not selection-ready from current-main governance truth alone.
- Queue inventory contains many bounded RDD tasks, but the queue explicitly says ready stock is not authoritative next-lane ranking by itself.
- Current-main planning surfaces do not clearly elevate one RDD continuation seam above the others as the strongest next governance move.

### Candidate D — Messaging follow-on
- Still live but unbounded.
- No third slice or bounded next messaging seam is clearly selected on current main.

### Candidate E — External validator / operator hardening residue
- Still live but not clearly ranked above the others.
- Current-main planning truth does not isolate one bounded governance-hardening tranche as the strongest next move.

## 6. RECOMMENDED_NEXT_WORKFRONT

`NO_STRONG_WORKFRONT_YET`

No single next bounded governance workfront is strongly enough supported by refreshed current-main truth.

## 7. WHY_THIS_NOW

- Phase 1 removed a false winner from current-main planning state.
- After that repair, the remaining candidates are either:
  - explicitly downgraded by later current-main evidence
  - live but still unbounded
  - present only as queue stock without stronger ranking proof
- Forcing a winner now would likely:
  - replay consumed work
  - elevate queue stock into fake authority
  - or reopen a lane current main already weakened
- What still blocks safe selection:
  - no remaining candidate has both clear current-main leverage and clean boundedness
  - current-main does not yet provide a decisive ranking artifact among RDD continuation, messaging follow-on, external hardening residue, or naming/boundary cleanup

## 8. BOUNDS_AND_INVARIANTS

- Do not replay the already-landed replay-outcome governance-evidence propagation tranche.
- Do not treat queue `Ready` status as sufficient ranking authority.
- Do not reopen AAT convergence contrary to the later current-main convergence spec.
- Do not infer a GovCore naming tranche as strongest without stronger current-main evidence.
- Preserve the refreshed planning truth:
  - formulation mode remains true
  - no single immediate winner is confirmed
- Any follow-on dispatch should first create a bounded comparison or clarification artifact rather than jumping straight to implementation.
