# Chain Verification / Terminal Judgment Design v1

## Objective
Define the bounded post-selector doctrinal lane that keeps chain verification coherent when triage outputs or terminal judgments supplement the already-consumed selector-mode sequence.

## Post-Selector Baseline
- The selector-mode tranche realized stage→shim→Gate C (`docs/dev/RDD_SELECTOR_MODE_TRANCHE_POST_IMPLEMENTATION_REVIEW__v1.md`), so triage outputs beyond that path lack a clear verification surface.
- The doctrine backlog (`docs/dev/GOVCORE_DESIGN_BACKLOG_EXTRACTION__v1.md`) and formulation (`docs/dev/POST_SELECTOR_DOCTRINE_FORMULATION__v1.md`) agree that chain verification across triage/terminal records is the highest-value next seam.

## Core Doctrinal Gap
Selector-mode only handles a single case-class path up to Gate C. The gap lies in verifying that chains containing triage outputs (e.g., UNDECIDED, PASS→TRIAGE) and terminal judgments still produce coherent, admissible history without replay or divergence.

## Problem Statement
Without deterministic checks over the enlarged chain (triage record ⇒ terminal record ⇒ Gate C result), operators cannot prove that doctrine continuity was maintained after selector-mode. The new tranche must provide explicit chain verification rules and terminal-presentation expectations.

## Bounded Lane Definition
### In-scope records/artifacts
1. Triaged record outputs (`triage_record.json`, e.g., `UNDECIDED`/`PASS` case classes).
2. Terminal judgment records that follow triage outputs (`terminal_record.json` with final outcomes and reason codes).
3. Gate C ledger entries showing how the chain reached a final `PASS`/`NON_ADMISSIBLE`.
4. Replay audit reports that include the triage+terminal sequences.

### Out-of-scope surfaces
- Selector-mode proofs already covered stage→shim→Gate C.
- Multi-case-class routing/mapping (Candidate C) is deferred; this lane stays on a single triage path.
- Validator/profile-specific metrics or proofs beyond deterministic chain integrity.
- Broader doctrine redesign or non-deterministic runbook work.

## Deterministic Verification Concept
Define a verification routine that:
1. Replays the triage+terminal sequence to ensure record hashes line up with Gate C ledger entries.
2. Verifies canonical order: triage record → optional terminal record → Gate C record with consistent `linked_records`.
3. Confirms no nonexistent transitions appear (e.g., triage→resolve skipped Gate C).
4. Emits bounded reason codes for mismatches (REPLAY_TRY_MISMATCH, TERMINAL_CHAIN_BREAK).

## Operator Evidence Concept
Operators will consume a `chain_verification_summary.jsonld` (or similar) that enumerates:
- verified record hashes for triage and terminal segments,
- Gate C ledger pointers,
- boolean coherence flag and reason codes,
- optional proof_packet link for the whole chain.

## Acceptance-Proof Concept
A future tranche must deliver:
- a deterministic summary proving the triage→terminal→Gate C chain was replayed successfully,
- targeted tests covering the specific triage/terminal pair with expected outcomes,
- example failure cases showing the verification catches mislinked records.

## False-Closure Cases
- Only documenting triage records without replay verification.
- Re-running selector-mode verification without the terminal record’s presence.
- Claiming coverage for multiple case classes when only one was specified.

## Next Control Step
Treat the chain-verification summary spec as the formulation artifact. The next tranche-selection task should implement the bounded verification and summary creation for one triage/terminal record combination, guided by this design.

## Evidence That Would Overturn The Design
- Current-main evidence showing no triage/terminal records remain unverified.
- Operator feedback prioritizing multi-case-class orchestration instead.
- A canonical artifact introducing a different verification seam (e.g., direct Gate inspection) that already satisfies the gap.
