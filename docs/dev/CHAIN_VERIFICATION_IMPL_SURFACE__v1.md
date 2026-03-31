# Chain Verification Impl-Surface Formulation v1

## Objective
Map the exact runtime and artifact surfaces required to implement Combo A chain verification so a bounded Task T404 implementation can be scoped or split appropriately.

## Current Combo A Baseline
- Triaged `UNDECIDED` record already emitted (FS_COPY dest-exists case, fixtures under `tests/fixtures/attestation_bundle/sample/` and `tests/test_policy_pass_undecided.sh`).
- Terminal `PASS` record exists but is not correlation-verified beyond Gate C logs.
- Gate C ledger entries (`system/scripts/aat-gate-c-wrapper.sh` output `aat_gate_c_ledger.jsonl`) already capture `triage_record_hash`, `terminal_record_hash`, `gate_record_hash`.
- Replay audit reports cover the entire chain; manifest verification sees the bundle but no dedicated summary.

## Required Runtime Surfaces
1. **Chain verification routine** living near the triage/Gate tooling (e.g., `scripts/verify-chain.py` or a new helper) that reads the triage record, terminal record, and Gate C ledger entry and computes hash/timestamp checks.
2. **Summary emitter** that writes `chain_verification_summary.json` after verification, ideally from the same script to keep runtime scope narrow.
3. **Test fixtures** in `tests/fixtures/attestation_bundle` representing the combo.

## Required Data/Artifact Surfaces
- Triaged record JSON (`triage_record.json`) with `policy_decision="UNDECIDED"` and `record_hash`.
- Terminal record JSON with `policy_decision="PASS"` and `linked_triage_hash`.
- Gate C ledger entry referencing the same hash trio (stored under `out/aat_gate_c_ledger.jsonl`).
- Replay audit containing the triage and terminal hashes for correlation.

## Minimal Correlation/Hash Logic
1. Compare `triage.record_hash` == `terminal.linked_triage_hash`.
2. Ensure Gate C entry’s `triage_record_hash` and `terminal_record_hash` match.
3. Assert monotonic timestamps: triage < terminal < Gate.
4. Generate `chain_verification_summary.json` with the schema from the Combo A spec (hashes, timestamps, result).

## chain_verification_summary.json Support
- New artifact required: file emitted by the verification routine, as per schema section of Combo A spec. It can be generated immediately after the checks without altering other artifacts.

## Classification
**SINGLE_BOUNDED_TASK.** All necessary surfaces (records, ledger, replay artifacts) already exist. Only one deterministic routine + summary generation + targeted tests need to be added, keeping the scope tight.

## Recommended Next Control Step
Draft the bounded implementation split: same task should add verification logic, emit `chain_verification_summary.json`, and add at least two tests (pass plus fail mismatch). This single tranche remains bounded and additive.

## Evidence That Would Overturn Classification
- Combo A artifacts already include such verification (no gap).  
- Operator guidance splits the work (e.g., separate correlation + summary tasks).  
- New doctrine artifacts require additional surfaces, forcing split.
