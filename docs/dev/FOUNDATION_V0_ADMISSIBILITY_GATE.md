# Foundation v0 Admissibility Gate

## Purpose
The Foundation v0 admissibility gate validates process constraints across a proof bundle and a process ledger.

Important boundary:
- Admissible output does **not** prove correctness of outcomes.
- Admissible output proves process constraints were satisfied by available artifacts.

## Output fields
- `ADMISSIBLE=YES|NO`
- `STOP_REQUIRED=YES|NO`
- `REASON_CODE=<code>`

## Interpretation
- `ADMISSIBLE=YES` and `STOP_REQUIRED=NO`
  - The gate found no admissibility violations.
- `ADMISSIBLE=NO` and `STOP_REQUIRED=NO`
  - Non-admissible process constraints were detected, but the run is classified as non-fatal.
- `ADMISSIBLE=NO` and `STOP_REQUIRED=YES`
  - Fatal conditions were detected and the run must stop.

## Reason-code classes
- `RC_OK`
  - No violations detected.
- Non-admissible examples:
  - `HASH_NOT_FOUND`
  - `ARTIFACT_HASH_MISMATCH`
  - `RULES_HASH_MISMATCH`
  - `STAMP_MISSING`
  - `STAMP_MISMATCH`
  - `SILENT_SURFACES`
- Stop-required examples:
  - `ENTRY_HASH_MISMATCH`
  - `CHAIN_BREAK`
  - `APPEND_SEQ_BREAK`
  - `SCHEMA_INVALID`
  - `SERIALIZATION_FAILURE`
  - `FV0_*` input/contract errors from the gate wrapper

## Operator actions
- If `STOP_REQUIRED=YES`:
  - Halt promotion and investigate the reported reason code first.
- If `ADMISSIBLE=NO` and `STOP_REQUIRED=NO`:
  - Treat as policy/process failure; remediation is required before admitting results.
- If `ADMISSIBLE=YES`:
  - Continue normal workflow checks.
