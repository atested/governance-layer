# TASK_206 — Evidence bundle indexer deterministic index.json

SPEC_EXPECTED: CODE

## Intent
Provide a deterministic evidence bundle indexer that produces stable `index.json` for evidence folders.

## Acceptance criteria
- Create a non-hot helper that emits deterministic JSON entries sorted by relative path.
- Include file path, sha256, and byte-size for each indexed file.
- Deterministic test proves identical output across run1/run2.

## Files allowed to touch
- system/tools/evidence_bundle_indexer.sh
- system/tests/test_evidence_bundle_indexer.sh
- docs/dev/evidence/TASK_206/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_206/TESTS.txt
- docs/dev/evidence/TASK_206/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_206/DIFF_STAT.txt
- docs/dev/evidence/TASK_206/HOTFILE_SCAN.txt

## Determinism expectations
- run1/run2 stdout SHA256 must match.

## STOP rules
- STOP if implementation requires touching hot files.
