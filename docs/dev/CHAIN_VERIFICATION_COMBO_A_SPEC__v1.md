# Chain Verification Combo A Spec v1

## Objective
Provide the concrete spec that Task T404 implementation will follow: deterministic verification/checks for the UNDECIDED triage → terminal PASS → Gate C PASS chain and the additive `chain_verification_summary.json` schema.

## Participating Records
1. **Triage record** (`triage_decision`): produced by `scripts/triage-eval.py` with `policy_decision` = `UNDECIDED`, `record_hash`, and `linked_record_hash` pointing to the preceding `pass_decision`.
2. **Terminal record** (`terminal_record`): generated immediately after the triage record, carrying the terminal `PASS` outcome and referencing the triage `record_hash` via `linked_triage_hash`.
3. **Gate C ledger entry** (`aat_gate_c_ledger.jsonl`): records the final Gate C `PASS`, including `triage_record_hash`, `terminal_record_hash`, and `gate_record_hash`.
4. **Replay audit report** and stored `proof_packet` (optional) for verifying the chain integrity.

## Deterministic Verification Checks
1. **Hash continuity**: `terminal_record.linked_triage_hash` equals `triage_record.record_hash`; `GateCEntry.triage_record_hash` equals `triage_record.record_hash`; the Gate C entry’s `terminal_record_hash` equals `terminal_record.record_hash`.
2. **Order enforcement**: triage record timestamp < terminal record timestamp < Gate C ledger timestamp.
3. **Decision coherence**: terminal record’s `policy_decision` = `PASS`, triage record `policy_decision` = `UNDECIDED`.
4. **Replay matching**: replay audit’s `record_hash` sequence includes both records, and `replay_audit_report.record_hash` equals Gate C triage hash.
5. **Reason code presence**: triage record includes expected reason codes (e.g., `dest_exists_no_overwrite`), and terminal record records the decision type.

## chain_verification_summary.json Schema
```json
{
  "schema_version": "chain_verification_summary_v1",
  "packet_id": "<proof_packet_id or null>",
  "chain": {
    "triage_record_hash": "sha256:<hex>",
    "terminal_record_hash": "sha256:<hex>",
    "gate_c_record_hash": "sha256:<hex>"
  },
  "timestamps": {
    "triage_record": "<iso8601>",
    "terminal_record": "<iso8601>",
    "gate_c": "<iso8601>"
  },
  "status": {
    "result": "PASS" | "FAIL",
    "reason_codes": ["RC-..."],
    "details": "human-readable summary"
  }
}
```

## Pass Condition
All verification checks succeed and `status.result` = `PASS`; the summary lists the linked hashes and timestamps, showing consistent chain ordering and associated reason codes.

## Fail-Closed Cases
1. **Hash mismatch**: terminal record’s `linked_triage_hash` or Gate C entry’s hashes do not align with stored record hashes → `status.result` = `FAIL`, reason `CHAIN_HASH_MISMATCH`.
2. **Order violation**: timestamps violate triage → terminal → Gate sequence → `status.result` = `FAIL`, reason `CHAIN_ORDER_VIOLATION`.
3. **Decision inconsistency**: triage record not `UNDECIDED` or terminal record not `PASS` → `status.result` = `FAIL`, reason `CHAIN_DECISION_MISMATCH`.

## Explicit Out-of-Scope
- Multi-case-class orchestration and other triage paths (Combo B/C)  
- Selector-mode pass sequences already verified  
- Broad doctrine redesign or validator-profile instrumentation  
- Any new artifacts beyond the defined summary JSON and verification routine

## Recommended Next Control Step
Use this spec to create the bounded implementation tranche: add the chain verification routine, emit `chain_verification_summary.json` after Combo A runs, and prove the fail-closed cases via tests.
