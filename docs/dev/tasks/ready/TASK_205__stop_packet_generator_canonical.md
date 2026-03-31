# TASK_205 — STOP PACKET generator canonical

SPEC_EXPECTED: CODE

## Intent
Add utility for canonical STOP PACKET emission with deterministic field ordering.

## Acceptance criteria
- Utility emits STOP PACKET with required fields in stable order.
- Supports injected step/command/output/status arguments.
- Deterministic tests verify output stability.

## Files allowed to touch
- system/tools/stop_packet_generator.sh
- system/tests/test_stop_packet_generator.sh
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_205/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_205/TESTS.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_205/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_205/DIFF_STAT.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_205/HOTFILE_SCAN.txt

## Determinism expectations
- Two-run output digest match required.

## STOP rules
- STOP if generator requires non-deterministic data sources at runtime.
