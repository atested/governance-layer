# RDD Selector-Mode Tranche Post-Implementation Review v1

Date: 2026-03-16
Reviewer: Codex
Scope: bounded post-implementation review of the current-v1-case-class selector-mode contract completion tranche

## Reviewed tranche-closure claim

Claim under review:

> The current-v1-case-class selector-mode contract family is materially closed as an execution-worthy RDD tranche, and the only implementation change needed on this branch was a bounded Darwin allow-root enforcement fix that lets the already-landed selector-mode contract logic execute end-to-end.

Review result: `supported`

## What was reviewed

- `scripts/policy-eval.py`
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh`
- `tests/test_rdd_triage_criteria_selector.sh`
- `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`
- `docs/dev/WORK_QUEUE.md` as context only

Note:
- The dispatch named `docs/dev/RDD_POST_PHASE11_TRANCHE_SELECTION__v1.md` as a primary source, but that file is not present on the branch. This did not block review because tranche truth was still recoverable from the implementation plan, queue context, code, and selector-mode test families.

## Decision against mandatory review questions

### 1. Does the implementation actually support the claimed tranche closure?

Yes.

The branch change is narrow but constitutive:

- before the change, the selector-mode family did not execute honestly on this host because `policy-eval.py` denied the bounded FS_COPY case as `OUTSIDE_ALLOWED_ROOT` before `rdd-pass-triage.sh` could invoke selector-mode triage
- after the change, the selector-mode wrapper reaches the already-landed selector-mode logic and the full selector contract matrix passes

That means the tranche claim is not that new doctrine logic was added here. The honest claim is that the existing selector-mode doctrine bundle was already present on main, but execution on the current host was blocked by a lower-level allow-root mismatch. The branch removes that blocker and restores the intended bounded selector-mode behavior.

### 2. Is the Darwin case-folded fallback in `under_base()` narrow, honest, and limited to intended host-filesystem behavior?

Yes.

The fallback:

- only runs after the ordinary `Path.relative_to()` check fails
- only runs on `sys.platform == "darwin"`
- only performs a case-folded equality/prefix comparison
- does not weaken traversal checks, hot-file checks, overwrite checks, or any selector-specific fail-closed rules

This is an honest host-filesystem compatibility fix for case-only path mismatches between shell-provided allow roots and Python-resolved request paths on the current macOS environment.

### 3. Does the change preserve non-Darwin behavior?

Yes.

Non-Darwin systems still return `False` after a failed `relative_to()` check, exactly as before. No non-Darwin policy path was changed.

### 4. Did the tranche stay bounded to the current v1 selector-mode family rather than widening into broader doctrine redesign?

Yes.

No broader RDD surfaces were changed. The branch edits only `scripts/policy-eval.py`, which sits on the execution path for the bounded selector-mode FS_COPY case class. No changes were made to:

- doctrine structure
- triage schema
- chain verification
- GovLayer or GovMCP runtime surfaces
- proof/export surfaces

### 5. Are the three selector-mode test families sufficient to justify the bounded tranche claim?

Yes, for this bounded claim.

They jointly cover:

- selector-mode invocation and routing behavior
- canonical request normalization and precedence
- legacy dual-alias conflict, mismatch, invalid-value, unsupported-value, normalized-equivalence, and case-normalization behavior
- explicit selector-map fail-closed behavior
- triage emission, chain linkage, and determinism

That is sufficient to justify the narrow claim that the selector-mode contract family now executes as intended for the current v1 case class.

### 6. Is any minimal corrective edit required before merge?

No.

## Scope / contract / code mismatches

No material code or contract mismatch was found.

Non-blocking documentation gap:

- the tranche-selection artifact named in the dispatch is absent on the branch under that exact path
- this is a review-input mismatch, not evidence of an inflated implementation claim

## Hidden widening or boundary leakage

None material.

The Darwin fallback does not reopen or widen:

- GovLayer-core trust-grade work
- GovMCP surfaces
- broader RDD continuation beyond the current v1 selector-mode family
- generic filesystem policy redesign

## Missing evidence

No material missing evidence for the bounded tranche claim.

The existing selector-mode test families provide direct end-to-end evidence that the branch restores execution of the already-landed selector-mode contract family on the current host.

## Merge readiness

Merge is safe as-is.

The bounded tranche-closure claim is justified exactly as:

- selector-mode contract completion for the current v1 case class is now executing end-to-end on this host
- the branch change is a bounded Darwin allow-root enforcement compatibility fix

It is not a claim of broader RDD completion or broader filesystem policy redesign.

## Corrective patch requirement

No corrective patch is required before merge.
