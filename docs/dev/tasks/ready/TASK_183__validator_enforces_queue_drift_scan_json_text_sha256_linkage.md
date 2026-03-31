# TASK_183__validator_enforces_queue_drift_scan_json_text_sha256_linkage.md

TASK_ID: TASK_183
Title: [External validator hardening] Enforce queue_drift_scan.json text_sha256 linkage in validator
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_183
Status: Ready
Dependencies: TASK_160
Bucket: External Usability Next
SPEC_EXPECTED: CODE

## Goal
Make `system/scripts/validate-proof-bundle.sh` fail closed when `queue_drift_scan.json` is present but its `text_sha256` does not match the bytes of `queue_drift_scan.txt`, while preserving optional-file absent semantics.

## Preconditions
- `system/scripts/validate-proof-bundle.sh` exists on the branch tip.
- `queue_drift_scan.json` optional emission semantics already exist (TASK_160 lineage).

## Files allowed to touch
- system/scripts/validate-proof-bundle.sh
- tests/test_validate_proof_bundle_qds_json_linkage_enforcement.sh
- docs/dev/evidence/TASK_183/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- system/scripts/release-gate.sh
- system/scripts/codex-unattended.sh
- README.md
- docs/EXTERNAL_CONTRACTS.md
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Validator enforces `queue_drift_scan.json` schema/linkage when the JSON file is present.
- Mismatch of `text_sha256` vs `queue_drift_scan.txt` bytes returns contract failure (`exit=1`) with a stable `FAIL:` marker.
- Missing optional `queue_drift_scan.json` remains INFO/PASS (`exit=0`) behavior.
- Deterministic test covers PASS, FAIL, and optional-absent cases with two-run digest equality.

## Deterministic test plan
1. Build a valid synthetic proof-bundle temp directory with `queue_drift_scan.txt` and matching `queue_drift_scan.json`.
2. Run validator twice on the valid case and compare normalized stdout/stderr digests.
3. Mutate `queue_drift_scan.json.text_sha256` to an incorrect value; run twice and assert `exit=1`, stable `FAIL:` marker, and identical digests.
4. Remove `queue_drift_scan.json`; run twice and assert optional-file INFO/PASS semantics and identical digests.
5. Record all commands, outputs, and `[exit=...]` markers in evidence.

## Evidence required
- docs/dev/evidence/TASK_183/TESTS.txt
- Transcript must include `$ ...` command lines and `[exit=...]` markers
- Include run1/run2 SHA256 digests for PASS/FAIL/optional-absent cases

## STOP conditions
- Stop if enforcing qds-json linkage requires edits outside the allowlist.
- Stop if validator exit taxonomy (`0/1/2`) would need broader refactoring to preserve determinism.
- Stop if current validator contract on branch tip is incompatible with the existing `queue_drift_scan_v1` payload shape (record a minimal repro).

## Return format
1) Summary
2) Files changed
3) qds-json linkage enforcement behavior (PASS/FAIL/optional absent)
4) Determinism digest proof
