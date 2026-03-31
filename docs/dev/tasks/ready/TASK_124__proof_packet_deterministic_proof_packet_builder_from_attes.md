# TASK_124__proof_packet_deterministic_proof_packet_builder_from_attes.md

TASK_ID: TASK_124
Title: [Proof packet] Deterministic proof-packet builder from attestation bundle + replay audit report
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_124
Status: Ready
Dependencies: TASK_110, TASK_111, TASK_115

## Goal
Add a deterministic proof-packet builder command that assembles an attestation bundle, replay audit report JSON, and a top-level proof manifest into a reproducible archive for audit handoff.

## Non-goals
- Do not broaden scope beyond the task goal.
- Do not weaken existing fail-closed behavior or determinism guarantees.
- Do not modify unrelated workflow/queue specs.

## Files allowed to touch
- scripts/attest/bundle.py
- scripts/replay-record.py
- scripts/proof-packet.py
- tests/test_proof_packet_build.sh
- tests/fixtures/attestation_bundle/**
- docs/dev/evidence/TASK_124/**

## Files forbidden to touch
- system/scripts/*
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Success criteria
- Produces a CODE diff (at least one non-evidence path changed).
- Updates `docs/dev/evidence/TASK_124/TESTS.txt` with commands and `[exit=...]` markers.
- Deterministic output/report/hash assertion passes across two runs for the task test plan.
- verify-task passes or reports deterministic SKIP only for explicit hard-dependency absence (with evidence).

## Deterministic test plan
1. Run the task-specific test runner twice against the same fixture/input set.
2. Capture SHA256 (or byte equality proof) for the primary output/report artifact and assert equality.
3. Run one controlled negative/sanity mutation (if task defines one) and assert deterministic exit/status.
4. Record the exact commands, outputs, and exit codes in the evidence file.

## Evidence required
- docs/dev/evidence/TASK_124/TESTS.txt
- Transcript must include `$ ...` command lines and `[exit=...]` markers
- Include the determinism digest values (run1 + run2) and PASS/FAIL summary

## STOP conditions
- If origin/main already contains the full behavior/tests for this task, stop and convert to a reconcile/provenance closeout (do not produce duplicate implementation branches).
- If required changes fall outside the allowlist, stop and request a minimal spec allowlist adjustment before proceeding.
- If output is nondeterministic across two runs, stop with a minimal repro (hashes, commands, fixture) before expanding scope.

## Return format
1) Summary
2) Files changed
3) Determinism proof (hashes / equality)
4) Test command(s) and exit codes
