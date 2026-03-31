# Current-Main Governance Design-Needed Backlog Extraction v1

## Why Now
- Canonical planning truth now records `NEXT_WORKFRONT_FORMULATION` and explicitly flags post-traceability governance evidence work as the current mode (`docs/dev/POST_REFRESH_NEXT_WORKFRONT_CONFIRMATION__v1.md`).
- Recent control-plane passes repeatedly discovered that families such as the deployment execution-path, AAT operator path, observability traceability, and messaging baseline slices were already consumed, leaving few unconsumed tranches (`docs/dev/FAMILY_CONSUMPTION_AND_LIVE_WORKFRONT_AUDIT__v1.md`).
- Record-to-packet coherence itself failed the fail-closed distinctness test (`docs/dev/GOVERNANCE_EVIDENCE_PRODUCT_RECORD_TO_PACKET_FORMULATION__v1.md`), which means the next useful work is to formulate a small design backlog rather than chase illusory tranches.

## Map
- **Consumed / reject**  
  - Deployment execution-path and external packaging families (`docs/dev/EXTERNAL_VALIDATOR_EXECUTION_PATH_FAMILY_CONSUMPTION__v1.md`, `docs/dev/EXTERNAL_PACKAGING_DISTRIBUTION_FAMILY_CONSUMPTION__v1.md`).  
  - AAT stage -> shim -> Gate C operator path.  
  - Evidence-path coherence candidates including record-to-packet edges (`docs/dev/GOVERNANCE_EVIDENCE_PRODUCT__EVIDENCE_PATH_COHERENCE_TRANCHE_SELECTION__v1.md`, `docs/dev/GOVERNANCE_EVIDENCE_PRODUCT_RECORD_TO_PACKET_FORMULATION__v1.md`).  
  - Messaging traceability/enhancement baseline.  

- **Design-blocked / worth formulating**  
  1. `AAT / Foundation v0 admissibility convergence restock candidate` (`docs/dev/AAT_POST_CONSUMPTION_RESELECTION__v1.md`).  
  2. `Post-selector doctrine continuation requiring bounded restock` (`docs/dev/RDD_POST_PHASE11_TRANCHE_SELECTION__v1.md`, `docs/dev/GOVCORE_REPO_WIDE_OPPORTUNITY_SCAN__v1.md`).  
  3. `Post-slice messaging follow-on (governed communications expansion)` as a follower on the messaging lane (`docs/dev/GOVCORE_REPO_WIDE_OPPORTUNITY_SCAN__v1.md`, `docs/dev/COMPARATIVE_TRANCHE_SELECTION__UNDERREPRESENTED_DIRECTIONS__v1.md`).

- **Too speculative / defer**  
  - Broad governance evidence product beyond current coherence candidates until a new unlinked artifact emerges.  
  - General GovMCP maturity repackaging, which the canon now marks as stale (`docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`, `docs/dev/CANONICAL_STATUS_AND_BASELINE_ALIGNMENT__v1.md`).  
  - Reference workflow / demonstration packaging, which remains downstream and low-yield (`docs/dev/GOVCORE_REPO_WIDE_OPPORTUNITY_SCAN__v1.md`).

## Prioritized Shortlist for Formulation

### 1. Immediate winner: AAT / Foundation v0 admissibility convergence restock
- **Why real?** The operator-path tranche is consumed, but `docs/dev/AAT_POST_CONSUMPTION_RESELECTION__v1.md` reports that convergence work is still live yet unbounded.  
- **Why not already consumed?** The convergence overlap with Foundation v0 and admissibility beyond Gate C is still unresolved; current-main has no canonical implementation yet.  
- **Blocking design question:** What bounded operator-facing story defines the convergence workfront (entry criteria, responsible surfaces, success metrics) so Codex can size the first tranche without reopening the consumed Gate C baseline?  
- **Formulation aim:** Define the convergence scope (e.g., which Foundation protocols and adm policies cross the Gate C outcome), the explicit artifacts/tests needed, and the evidence/acceptance tokens that would prove the restock is distinct from the consumed operator path.  
- **Notes:** This formulation will allow a later tranche-selection pass to issue a claim-safe implementation batch that ties admissibility semantics to the emerging Foundation layer.

### 2. Backup: Post-selector doctrine continuation requiring bounded restock
- **Why real?** The RDD selector-mode tranche is closed, but `docs/dev/RDD_POST_PHASE11_TRANCHE_SELECTION__v1.md` and the opportunity scan show conceptual work still lives in the doctrine continuation lane.  
- **Why not consumed?** No further bounded tranche has been successfully isolated on current main; the published artifacts only cover the selector-mode finish, not the next doctrinal seam.  
- **Blocking design question:** Which doctrinal surface (e.g., triage evaluator, chain verification, external proof interplay) should the next continuation address, and what are its success criteria/dry-run acceptance cases so we avoid the speculative, low-yield queue entries?  
- **Formulation aim:** Outline the doctrinal metrics, targeted artifacts, and per-task acceptance constraints required to keep the next tranche bounded and distinct.  
- **Notes:** This will discipline the RDD lane away from merely replaying restocked UNDECIDED seams and toward the next credible doctrinal instrument.

## Explicit “Do Not Pursue Now”
- **Record-to-packet coherence candidates** (replay audit → proof-packet, verifier-summary fusion) failed the distinctness checklist and would duplicate consumed proof/export parity (`docs/dev/GOVERNANCE_EVIDENCE_PRODUCT_RECORD_TO_PACKET_FORMULATION__v1.md`).  
- **Governance evidence product generalization without a new artifact** lacks a defendable gap and drifts into reporting/dashboard fantasies (`docs/dev/GOVERNANCE_EVIDENCE_PRODUCT_WORKFRONT_FORMULATION__POST_TRACEABILITY__v1.md`).  
- **Messaging follow-on beyond formulating a new bounded bundle** is noted for the future but currently lacks separation from the baseline; treat it as higher-order backlog until the other two tasks ship.  
- **General GovMCP maturity** is stale and would only recycle consumed baseline semantics (`docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`).

## Summary
- **Immediate formulation winner:** AAT / Foundation v0 admissibility convergence restock (design question + scope defined above).  
- **Backup formulation candidate:** Post-selector doctrine continuation requiring bounded restock.  
- **Project blockage:** The repo is presently more blocked by missing workfront definitions than by missing implementation; most remaining families either need tighter formulation (above) or are already consumed.  
- **Next control step:** Run these two bounded formulation passes (winner first) to capture missing design detail, then re-attempt tranche selection once the formulation outputs show a distinct, bounded workfront.  
- **Evidence that would overturn the ranking:** emergence of a new unconsumed evidence artifact (e.g., a missing Foundation admissibility hook or an RDD brace with clear boundaries), a canonical formulation showing the record-to-packet gap is new, or a fresh request highlighting a different high-leverage need.
