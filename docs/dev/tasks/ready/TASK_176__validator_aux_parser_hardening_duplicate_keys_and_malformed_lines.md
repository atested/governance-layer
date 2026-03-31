# TASK_176__validator_aux_parser_hardening_duplicate_keys_and_malformed_lines.md

TASK_ID: TASK_176
Title: [External validator hardening] Aux parser hardening (duplicate keys and malformed lines)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_176
Status: Ready
Dependencies: TASK_154, TASK_143
Bucket: External Validator Hardening
SPEC_EXPECTED: CODE

## Goal
Add deterministic tests (and minimal validator edits only if required) for `validate-proof-bundle.sh` aux-file parsing of `versions.txt` and `release_gate_log.txt`, covering duplicate keys, malformed lines, and failure taxonomy stability.

## Preconditions
- `system/scripts/validate-proof-bundle.sh` exists on the branch tip.
- Validator checks aux files during proof-bundle validation.

## Files allowed to touch
- tests/test_validate_proof_bundle_aux_parser_hardening.sh
- system/scripts/validate-proof-bundle.sh
- docs/dev/evidence/TASK_176/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- system/scripts/release-gate.sh
- system/scripts/codex-unattended.sh
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Deterministic aux-parser hardening test exists and covers duplicate keys, empty keys, and malformed non-`key=value` lines.
- Validator emits stable FAIL/ERROR taxonomy if edits are required.
- Evidence transcript proves deterministic digests across repeated runs.

## Deterministic test plan
1. Construct temporary proof-bundle directories with malformed aux files.
2. Run validator twice per representative case.
3. Assert exit taxonomy (`1` contract violation, `2` runtime error) and stable markers.

## Evidence required
- docs/dev/evidence/TASK_176/TESTS.txt

## STOP conditions
- Stop if `validate-proof-bundle.sh` is missing on the branch tip (dependency TASK_154 not merged).
- Stop if hardening requires edits outside allowlist.
- Stop if validator semantics are ambiguous and require contract clarification beyond deterministic tests.

## Return format
1) Summary
2) Files changed
3) Taxonomy behavior (PASS/FAIL/ERROR)
4) Determinism digest proof
