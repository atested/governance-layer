# TASK_187__external_contracts_optional_outputs_consistency_fix.md

TASK_ID: TASK_187
Title: [External packaging docs consistency] EXTERNAL_CONTRACTS optional outputs consistency fix (`queue_drift_scan.json`)
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_187
Status: Ready
Dependencies: TASK_167, TASK_171
Bucket: External Usability Next
SPEC_EXPECTED: CODE

## Goal
Ensure `docs/EXTERNAL_CONTRACTS.md` explicitly lists `queue_drift_scan.json` as an optional proof-bundle output so the docs consistency enforcement test passes when `docs/DISTRIBUTION.md` is present.

## Preconditions
- `docs/EXTERNAL_CONTRACTS.md` exists on the branch tip.
- If `tests/test_external_docs_contract_consistency.sh` is absent on `origin/main`, this task may add it solely to provide deterministic evidence for the docs consistency contract checks.

## Files allowed to touch
- docs/EXTERNAL_CONTRACTS.md
- tests/test_external_docs_contract_consistency.sh
- docs/dev/evidence/TASK_187/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- docs/dev/tasks/ready/**
- README.md
- system/scripts/*
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- `docs/EXTERNAL_CONTRACTS.md` optional outputs section includes `queue_drift_scan.json` without changing the required-file contract.
- Evidence includes the exact grep anchors used by the docs consistency test.
- Docs consistency test runs twice with deterministic output digest equality (PASS if dependencies present, deterministic SKIP if `docs/DISTRIBUTION.md` absent).

## Deterministic test plan
1. Run grep(s) that verify `docs/EXTERNAL_CONTRACTS.md` contains optional `queue_drift_scan.json` references and additive wording remains intact.
2. Run `tests/test_external_docs_contract_consistency.sh` twice and capture output digests.
3. If `docs/DISTRIBUTION.md` is absent, assert deterministic INFO/SKIP (`rc=3`) rather than FAIL.
4. Record commands, outputs, and `[exit=...]` markers in evidence.

## Evidence required
- docs/dev/evidence/TASK_187/TESTS.txt

## STOP conditions
- Stop if fixing docs consistency requires editing files outside the allowlist.
- Stop if the docs consistency test requires broadening beyond `tests/test_external_docs_contract_consistency.sh`.

## Return format
1) Summary
2) Files changed
3) Docs consistency grep proof
4) Determinism digest proof
