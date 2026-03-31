# AAT v0 Gate B Contract

## Purpose
Gate B takes AAT Gate A outputs and appends deterministic audit events to the Foundation v0 process ledger.

## Inputs
- `aat_action_record` JSON (action context)
- `decision_record` JSON (ADR from Gate A)
- `proof_bundle_manifest` JSON (contains `coverage_stamp_ref`)
- `rules_snapshot` JSON
- `ledger` path

## Ledger append model
Gate B appends exactly two entries per invocation:
1. `aat_action_event`
2. `aat_decision_event`

Both entries are append-only JSONL ledger rows created through `scripts/foundation_v0_process_ledger.py append`.

## Canonical append fields
Each append uses canonical-domain fields already defined by Foundation v0:
- `append_seq`
- `prev_entry_hash`
- `operation_id`
- `capability_surfaces`
- `decision_record_ref`
- `proof_bundle_ref`
- `rules_ref`
- `input_artifact_refs`

Metadata is allowed but never inserted into canonical hash domain.

## Typed refs and payload policy
- Ledger stores only typed refs + hashes.
- Payload bodies are not embedded in ledger entries.
- Required typed refs: `decision_record`, `proof_bundle`, `rules_version`, `input_file`.
- Gate B also requires catalog registration for `action_decision_record` for AAT decision governance.

## Outcome mapping
Gate B maps ADR outcomes to wrapper result lines and exit behavior:
- `PASS` -> `ADMISSIBLE=YES`, `STOP_REQUIRED=NO`, exit `0`
- `FAIL_NON_ADMISSIBLE` -> `ADMISSIBLE=NO`, `STOP_REQUIRED=NO`, exit `1`
- `FAIL_HARD_STOP` -> `ADMISSIBLE=NO`, `STOP_REQUIRED=YES`, exit `2`

`REASON_CODE` is the first ADR reason code when present, otherwise `NONE`.

## Hard-stop conditions in Gate B layer
Gate B exits hard-stop (`STOP_REQUIRED=YES`, exit `2`) when:
- required inputs are missing
- ADR decision is invalid
- typed-ref catalogs are missing required types
- ledger append fails for either required event append
