# Chain Verification Tranche Selection v1

## Objective
Determine whether a bounded execution tranche can be isolated for the Chain Verification / Terminal Judgment extension described in the doctrinal spec, focusing on one triage/terminal/Gate C record combination.

## Candidate Combinations Considered
- **Combo A:** UNDECIDED triage record → terminal PASS/RETRY record → Gate C PASS ledger entry (uses FS_COPY dest-exists case class)
- **Combo B:** PASS triage record → terminal NON_ADMISSIBLE judgment → Gate C NON_ADMISSIBLE ledger entry
- **Combo C:** UNDECIDED triage record → terminal REFUSE judgement → Gate C NON_ADMISSIBLE ledger entry

## Distinctness / Readiness
- **Combo A:** Distinct because current selector-mode work only captures the single PASS path; adding UNDECIDED→terminal→Gate chain verification is new. Execution-ready: mixed; artifacts already exist (`scripts/aat-gate-c-wrapper.sh`, ledger json) but no verification summary yet. → **Execution-ready if bounded (tranche qualifies)**  
- **Combo B:** Distinct and builds on existing terminal judgment instrumentation; similar to Combo A but handles non-admissible outcomes. Execution-ready: yes once bounded.  
- **Combo C:** Distinct but less immediate because it mixes UNDECIDED with refusal; might be better for later tranche.

## Recommended First Tranche
**Combo A** (UNDECIDED triage → terminal PASS → Gate C PASS) is the recommended bounded target because it stays closest to the consumed selector path while still adding triage/terminal coverage.

### Exact Minimum Tranche Definition
- Files/artifacts: `aat_gate_c_ledger.jsonl`, triage/terminal record fixtures under `evidence/aat`, `scripts/replay-record.py`, and new `chain_verification_summary.json` produced post-replay.
- Deterministic checks: ensure triage→terminal hashes match Gate C ledger entries, counts, and reason codes; emit specific reason codes for misordered chains.
- Operator evidence: the new summary must list record hashes, Gate C offsets, and boolean pass flag.
- Exclusions: do not touch selector-mode code, multi-case-class routing, validator-specific metrics, or proof-export surfaces.

## Execution-Ready Now?
**YES**, for Combo A once the summary spec is implemented; the existing artifacts provide the data, so the next step is bounded verification logic and summary emission.

## Minimum Next Control Step
Formulate the specific chain-verification implementation task by detailing the verification routine, summary output schema, and acceptance tests for Combo A; this prepares a claim-ready tranche.

## Evidence That Would Overturn This Recommendation
- Canonical main evidence shows Combo A already verified (no gap)  
- Operator guidance prioritizes Combo B/C instead  
- A new artifact makes Combo A outdated (e.g., multi-case-class orchestration already implemented)
