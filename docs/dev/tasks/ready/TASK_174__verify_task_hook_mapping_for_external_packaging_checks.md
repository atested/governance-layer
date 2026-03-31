# TASK_174__verify_task_hook_mapping_for_external_packaging_checks.md

TASK_ID: TASK_174
Title: [External packaging tranche 2] Verify-task hook mapping for external packaging checks
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_174
Status: Ready
Dependencies: TASK_170, TASK_171, TASK_172, TASK_173
Bucket: External Usability Next

## Goal
Extend verify-task hook mapping so TASK_170-173 run the correct external packaging test scripts with deterministic OK/FAIL/SKIP/INFO taxonomy.

## Preconditions
- `system/scripts/codex-unattended.sh` verify-task command exists on origin/main.

## Files allowed to touch
- system/scripts/codex-unattended.sh
- docs/dev/evidence/TASK_174/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- verify-task maps TASK_170-173 to the correct scripts with deterministic taxonomy and stable messaging.
- Evidence transcript proves deterministic verify-task summary digest across two runs.

## Deterministic test plan
1. Run `bash system/scripts/codex-unattended.sh verify-task TASK_171`, `TASK_172`, and `TASK_173`.
2. Run `verify-task TASK_170` without `PROOF_BUNDLE_DIR` and assert deterministic SKIP/INFO behavior.
3. Run the sequence twice and compare summary digests.

## Evidence required
- docs/dev/evidence/TASK_174/TESTS.txt

## STOP conditions
- Stop if verify-task taxonomy would need global semantic changes beyond adding TASK_170-173 mappings.
- Stop if changes spill outside allowlist.

## Return format
1) Summary
2) Files changed
3) Verify-task mapping behavior
4) Verify commands and exit codes
