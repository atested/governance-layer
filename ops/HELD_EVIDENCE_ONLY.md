# HELD_EVIDENCE_ONLY.md

Audit log of evidence-only branches held (not merged to main).

Evidence-only branches contain only changes under `docs/dev/evidence/` and are held by default to keep main clean. This file provides an audit trail showing what evidence exists but remains unmerged.

---

## 2026-02-24 Morning Merge (Post CODE-only merge)

**Timestamp**: 2026-02-24T09:00EST
**Total held**: 26 evidence-only branches
**Total conflicts**: 6 CODE variant branches (alternative implementations)

### Evidence-only branches held (26)

| Branch | Task ID | Hash | Status |
|---|---|---|---|
| origin/codex/TASK_022__53c6c2e | TASK_022 | 53c6c2e | Held - evidence only |
| origin/codex/TASK_030__7c161a5 | TASK_030 | 7c161a5 | Held - evidence only |
| origin/codex/TASK_031__4aad760 | TASK_031 | 4aad760 | Held - evidence only |
| origin/codex/TASK_032__570411b | TASK_032 | 570411b | Held - evidence only |
| origin/codex/TASK_050__8b4ba52 | TASK_050 | 8b4ba52 | Held - evidence only |
| origin/codex/TASK_051__1ddb748 | TASK_051 | 1ddb748 | Held - evidence only |
| origin/codex/TASK_060__5fe95bf | TASK_060 | 5fe95bf | Held - evidence only |
| origin/codex/TASK_061__41cf382 | TASK_061 | 41cf382 | Held - evidence only |
| origin/codex/TASK_062__e75c001 | TASK_062 | e75c001 | Held - evidence only |
| origin/codex/TASK_063__c9f58ef | TASK_063 | c9f58ef | Held - evidence only |
| origin/codex/TASK_064__739b939 | TASK_064 | 739b939 | Held - evidence only |
| origin/codex/TASK_065__855d71e | TASK_065 | 855d71e | Held - evidence only |
| origin/codex/TASK_066__eb98c61 | TASK_066 | eb98c61 | Held - evidence only |
| origin/codex/TASK_067__73e85f3 | TASK_067 | 73e85f3 | Held - evidence only |
| origin/codex/TASK_069__a52b7dc | TASK_069 | a52b7dc | Held - evidence only |
| origin/codex/TASK_080__0f8355e | TASK_080 | 0f8355e | Held - evidence only |
| origin/codex/TASK_081__5f1512d | TASK_081 | 5f1512d | Held - evidence only |
| origin/codex/TASK_099__28ef8e8 | TASK_099 | 28ef8e8 | Held - evidence only |
| origin/codex/TASK_099__9e877e8 | TASK_099 | 9e877e8 | Held - evidence only |
| origin/codex/TASK_101__bd660cc | TASK_101 | bd660cc | Held - evidence only |
| origin/codex/TASK_102__2e94724 | TASK_102 | 2e94724 | Held - evidence only |
| origin/codex/TASK_103__8b8fba3 | TASK_103 | 8b8fba3 | Held - evidence only |
| origin/codex/TASK_104__1027126 | TASK_104 | 1027126 | Held - evidence only |
| origin/codex/TASK_105__3d6775e | TASK_105 | 3d6775e | Held - evidence only |
| origin/codex/TASK_106__66233aa | TASK_106 | 66233aa | Held - evidence only |
| origin/codex/TASK_107__26ffbc1 | TASK_107 | 26ffbc1 | Held - evidence only |

### CODE variant branches held due to conflicts (6)

These branches contain CODE changes but conflict with already-merged implementations:

| Branch | Task ID | Hash | Conflict |
|---|---|---|---|
| origin/codex/TASK_096__740ce75 | TASK_096 | 740ce75 | Conflicts with merged TASK_096__2b04dc2 |
| origin/codex/TASK_096__9a6811e | TASK_096 | 9a6811e | Conflicts with merged TASK_096__2b04dc2 |
| origin/codex/TASK_096__aec76ce | TASK_096 | aec76ce | Conflicts with merged TASK_096__2b04dc2 |
| origin/codex/TASK_097__a36af13 | TASK_097 | a36af13 | Conflicts with merged TASK_097__41190f7 |
| origin/codex/TASK_098__043ca48 | TASK_098 | 043ca48 | Conflicts with merged TASK_098__1b2b9b5 |
| origin/codex/TASK_098__1f0d3ad | TASK_098 | 1f0d3ad | Conflicts with merged TASK_098__1b2b9b5 |

**Policy note**: Evidence-only branches are held by default. They can be merged on explicit request but are not required for main to remain functional.

---

## 2026-02-24 Afternoon Merge (Post documentation + new CODE branches)

**Timestamp**: 2026-02-24T12:10EST
**Total held**: 26 evidence-only branches (unchanged)
**Total conflicts**: 6 CODE variant branches (unchanged)
**CODE branches merged**: 2 (TASK_101__99dbebe, TASK_107__b040deb)

### Changes since morning merge
- ✓ Merged TASK_101__99dbebe - Signing Phase 3: implement verifier support for signatures
- ✓ Merged TASK_107__b040deb - Evidence standardization: add helper to write test evidence
- Note: TASK_107__26ffbc1 (evidence-only variant) remains held

### Current state
All new CODE branches merged. Remaining 32 unmerged branches:
- 26 evidence-only branches (same as morning)
- 6 CODE variant branches (conflict alternatives, held)

**No action required**: Evidence-only branches held per policy.

---

## 2026-02-24 Policy Correction (TASK_105 revert)

**Timestamp**: 2026-02-24T15:07EST
**Action**: Reverted mistaken merge of EVIDENCE_ONLY branch

### Incident Summary

**What happened**:
- TASK_105__af3ad7c was labeled as CODE in merge request
- Branch only changed `docs/dev/evidence/TASK_105/TESTS.txt` (EVIDENCE_ONLY)
- Merged to main (commit d73df96) despite being EVIDENCE_ONLY
- Violated "CODE-only on main" policy

**Correction taken**:
- Reverted merge commit d73df96 using `git revert -m 1` (commit d2a0823)
- Removed TASK_105 entry from ASSIGNMENTS.md
- No history rewrite (clean revert)

**Current status**:
- origin/codex/TASK_105__af3ad7c remains available as held EVIDENCE_ONLY branch
- Can be merged on explicit exception request
- Default policy reinforced: merge CODE only, hold EVIDENCE_ONLY

### Held branch record

| Branch | Task ID | Hash | Status |
|---|---|---|---|
| origin/codex/TASK_105__af3ad7c | TASK_105 | af3ad7c | Held - evidence only (mistakenly merged, reverted) |

**Rationale for revert**: Preserving "CODE-only on main" prevents policy drift. One-time exceptions create precedent and ambiguity. Clean revert maintains clear governance boundary.

---

## 2026-02-24 Post-Correction Merge Window

**Timestamp**: 2026-02-24T15:20EST
**CODE branches merged**: 1 (TASK_106__4d97ba5)
**EVIDENCE_ONLY branches held**: 1 new (TASK_104__cbbf36a)

### Changes
- ✓ Merged TASK_106__4d97ba5 (CODE) - Signing key loading: implement deterministic key derivation helpers and tests
- ⊗ Held TASK_104__cbbf36a (EVIDENCE_ONLY) - only changes `docs/dev/evidence/TASK_104/TESTS.txt`

### New held branch

| Branch | Task ID | Hash | Status |
|---|---|---|---|
| origin/codex/TASK_104__cbbf36a | TASK_104 | cbbf36a | Held - evidence only |

**Status check completed**:
- TASK_107__df43a8f: Already merged (commit 34d46ba)
- TASK_104__cbbf36a: Classified EVIDENCE_ONLY, held per policy
- TASK_106__4d97ba5: Classified CODE, merged successfully

**Policy confirmed**: CODE-only on main. EVIDENCE_ONLY branches held by default unless explicit exception requested.

---

## 2026-02-25 TASK_002 Branch Consolidation

**Timestamp**: 2026-02-25T08:35EST
**Decision**: Hold EVIDENCE_ONLY consolidated note; retire superseded branches

### Context
TASK_002 is CODE-expected (allowlist includes task specs, WORK_QUEUE, ASSIGNMENTS). Three published branches exist:
- `origin/codex/TASK_002__32c3d9d` - CODE (evidence + task spec modification)
- `origin/codex/TASK_002__65949ff` - CODE (evidence + task spec modification)
- `origin/codex/TASK_002__CONSOLIDATED__00e18ac` - EVIDENCE_ONLY (consolidation note explaining supersession)

WORK_QUEUE_RECONCILE merge (05ed035) already incorporated normalized TASK_002 allowlist to origin/main, making the CODE changes in the first two branches obsolete.

### Action
- ⊗ Held `origin/codex/TASK_002__CONSOLIDATED__00e18ac` (EVIDENCE_ONLY)
- ⊗ Retired `origin/codex/TASK_002__32c3d9d` (superseded by WORK_QUEUE_RECONCILE)
- ⊗ Retired `origin/codex/TASK_002__65949ff` (superseded by WORK_QUEUE_RECONCILE)

### Held branch record

| Branch | Task ID | Hash | Status |
|---|---|---|---|
| origin/codex/TASK_002__CONSOLIDATED__00e18ac | TASK_002 | 00e18ac | Held - evidence only (consolidation note) |

### Superseded branches (do not merge)

| Branch | Task ID | Hash | Status |
|---|---|---|---|
| origin/codex/TASK_002__32c3d9d | TASK_002 | 32c3d9d | Superseded - CODE changes incorporated via WORK_QUEUE_RECONCILE__05ed035 |
| origin/codex/TASK_002__65949ff | TASK_002 | 65949ff | Superseded - CODE changes incorporated via WORK_QUEUE_RECONCILE__05ed035 |

**Rationale**: TASK_002 remains CODE-expected in WORK_QUEUE. Consolidated branch is evidence-only documenting supersession. Per "CODE-only on main" policy, holding evidence-only branch. The two older branches had their CODE content (allowlist normalization) merged via WORK_QUEUE_RECONCILE, making them obsolete.

**Next steps**: If TASK_002 execution completes, a new CODE branch with task spec/queue updates will be required. The consolidated evidence note can be incorporated at that time or merged separately on explicit exception.

---
