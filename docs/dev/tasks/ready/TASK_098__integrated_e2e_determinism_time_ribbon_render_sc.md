# TASK_098__integrated_e2e_determinism_time_ribbon_render_sc.md

TASK_ID: TASK_098
Title: Integrated E2E determinism: time ribbon render schema strict and stable
Executor: CODEX
Branch: codex/TASK_098
Status: Ready
Dependencies: []

## Goal
Ensure time ribbon renderer fails closed on missing required fields (speculation_tag) and renders deterministically with stable ordering.

## Non-goals
No UI; text output only.

## Files allowed to touch
- docs/dev/evidence/TASK_098/**
- scripts/attest/**
- tests/test_integrated_negative_bad_time_ribbon.sh
- tests/fixtures/integrated_e2e/**
## Files forbidden to touch
[]

## Procedure
1) Enforce strict schema validation for time ribbon inputs; fail closed if required fields are missing (e.g. speculation_tag).
2) Ensure deterministic rendering:
   - stable ordering of events/items
   - stable serialization
3) Add negative tests:
   - missing speculation_tag fixture must fail closed
   - unsorted inputs must still render deterministically (sort internally)
4) Evidence:
   - docs/dev/evidence/TASK_098/TESTS.txt includes $ commands and [exit=...] markers for the test run.
## Acceptance criteria


- time ribbon renderer fails closed on missing required fields (speculation_tag).
- rendering is deterministic across runs (stable ordering enforced).
- tests/test_integrated_negative_bad_time_ribbon.sh passes and covers:
  - missing speculation_tag fixture
  - unsorted input fixture
## Evidence required


- docs/dev/evidence/TASK_098/TESTS.txt with:
  - test command(s)
  - exit markers
  - pass/fail summary output
## Return format
Return:
- files changed
- what fields are required and how failure is enforced
- ordering rule for determinism
- test command + output summary
