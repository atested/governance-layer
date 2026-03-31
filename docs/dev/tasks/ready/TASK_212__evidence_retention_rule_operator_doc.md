# TASK_212 — Evidence retention rule operator doc

SPEC_EXPECTED: CODE

## Intent
Document required evidence artifacts and placement rules for operators.

## Acceptance criteria
- Operator-facing doc defines minimum required artifacts per branch/task.
- Includes deterministic examples of valid paths.
- Add doc test validating required headings/tokens.

## Files allowed to touch
- docs/design/evidence_retention_rules.md
- system/tests/test_evidence_retention_rules_doc.sh
- docs/dev/evidence/TASK_212/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_212/TESTS.txt
- docs/dev/evidence/TASK_212/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_212/DIFF_STAT.txt
- docs/dev/evidence/TASK_212/HOTFILE_SCAN.txt

## Determinism expectations
- run1/run2 stdout SHA256 must match.

## STOP rules
- STOP if doc updates require modifying WORK_QUEUE or ASSIGNMENTS.
