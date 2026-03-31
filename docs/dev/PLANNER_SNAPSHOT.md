# Planner Snapshot

## Current State

- Codex is Codex CLI only.
- codex-batch is read-only, deterministic, artifact-safe; writes ops/CODEX_BATCH.txt without claiming or editing WORK_QUEUE.
- FS reason code machinery exists:
  - scripts/policy-eval.py defines RC-FS-* constants and emits cap_registry_hash
  - scripts/verify-record.py enforces cap_registry_hash
  - scripts/replay-record.py compares reason codes and cap_registry_hash during replay
- RC test tasks exist under docs/dev/tasks/ready (TASK_062..TASK_067).
- Evidence paths were expanded for TASK_062..TASK_065 to allow docs/dev/evidence/TASK_06X/**.

## Problem

Operational knowledge is distributed across scripts and implicit conventions. This causes rediscovery and contradictions (example: merge-queue.sh vs "Cecil sole merger").

## Plan

1) Canonicalize ops:
- Maintain docs/dev/OPS_CANONICAL.md as single source of truth.

2) Deterministic inventory:
- system/scripts/inventory-snapshot.sh generates docs/dev/inventory/INVENTORY_LATEST.md.

3) Enforce drift detection:
- scripts/verify-ops-canonical.py fails if canonical docs or inventory are missing, or if scripts introduce merge-to-main behavior without explicit classification.

4) Next after canonicalization:
- Add a Codex unattended gatekeeper runner for per-task preflight, Allowed Files enforcement, evidence enforcement, commit, and push.
