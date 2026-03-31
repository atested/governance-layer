# Phase 1 Implementation Plan: Operating Model Improvement

Version: v0 (planning draft)
Status: Implementation planning — not yet authorized for implementation
Scope: Phase 1 only — dispatch operating card, shared current-conditions store, Codex reception checklist

## 1. Phase 1 Goals

1.1. Establish a mandatory dispatch standard for all ChatGPT-to-Codex work.
1.2. Create a shared current-conditions store at `docs/dev/CURRENT_CONDITIONS.md` that ChatGPT, Codex, and Cecil can all consult.
1.3. Define a Codex reception checklist that validates incoming dispatches before execution begins.
1.4. Achieve these goals without modifying existing canonical files (OPS_PROCESS v1, OPS_CANONICAL, DISPATCH_LIBRARY v10, MERGE_GATE, AGENT_CONTRACT, RUNBOOK, BFPS v12).
1.5. Establish the foundation for Phases 2–5 without pulling later-phase scope into Phase 1.

## 2. In-Scope Artifacts

| Artifact | Location | Purpose |
|---|---|---|
| Dispatch operating card spec | `docs/dev/specs/DISPATCH_OPERATING_CARD__SPEC__v0.md` | Specification for ChatGPT dispatch behavior |
| Current conditions store spec | `docs/dev/specs/CURRENT_CONDITIONS__SPEC__v0.md` | Specification for shared current-state file |
| Codex reception checklist spec | `docs/dev/specs/CODEX_RECEPTION_CHECKLIST__SPEC__v0.md` | Specification for Codex dispatch validation |
| Current conditions store (runtime) | `docs/dev/CURRENT_CONDITIONS.md` | The live shared-state file itself |
| Dispatch operating card (GPT project copy) | GPT project file (external to repo) | ChatGPT working copy of dispatch rules |

## 3. Out-of-Scope Items

The following are explicitly out of scope for Phase 1:

1. Edits to OPS_PROCESS v1, OPS_CANONICAL, DISPATCH_LIBRARY v10, MERGE_GATE, AGENT_CONTRACT, RUNBOOK, or BFPS v12
2. Investigation-mode artifacts or landing-zone creation (`docs/dev/analysis/`)
3. Merge-prep report format or merge-prep delegation
4. Cecil feedback channel implementation
5. QT/sisters integration model
6. Reset-condition framework beyond the minimal always-on line
7. Cost/throughput measurement beyond what naturally appears in reports
8. OPS_PROCESS v2 drafting
9. Report format canonization as a standalone artifact (formats are defined in specs but not yet a separate reference document)

## 4. Implementation Sequencing

### 4.1. Dependency Order

```
CURRENT_CONDITIONS__SPEC__v0.md
    ↓ (defines store schema that dispatch card references)
DISPATCH_OPERATING_CARD__SPEC__v0.md
    ↓ (defines dispatch standard that reception checklist validates)
CODEX_RECEPTION_CHECKLIST__SPEC__v0.md
```

The current-conditions spec MUST be authored first because the dispatch operating card references the store for batch coherence checks and shared-state reads.

The dispatch operating card spec MUST be authored second because the Codex reception checklist validates the dispatch envelope defined by the card.

The reception checklist spec MUST be authored third because it depends on both prior artifacts.

### 4.2. Smallest Viable Implementation Order

1. Author `CURRENT_CONDITIONS__SPEC__v0.md` (defines the store contract)
2. Author `DISPATCH_OPERATING_CARD__SPEC__v0.md` (defines ChatGPT dispatch behavior)
3. Author `CODEX_RECEPTION_CHECKLIST__SPEC__v0.md` (defines Codex validation behavior)
4. Create the live `docs/dev/CURRENT_CONDITIONS.md` file with initial schema
5. Copy the dispatch operating card content to GPT project file
6. Pilot: run 3–5 real dispatches using the new standard
7. Evaluate: assess startup speed, output quality, store usefulness, format overhead

## 5. Artifact Coexistence with Existing Documents

Phase 1 artifacts coexist with existing documents as follows:

| Existing Artifact | Phase 1 Relationship | Action |
|---|---|---|
| OPS_PROCESS v1 | Dispatch operating card extends Section 9.1 with richer dispatch structure. OPS_PROCESS v1 remains authoritative for role definitions, task creation rules, evidence contract, and merge strategy. | No change to OPS_PROCESS v1. Dispatch card references OPS_PROCESS v1 for inherited requirements. |
| OPS_CANONICAL | Unaffected. Lanes, invariants, and script registry are unchanged. | No change. |
| DISPATCH_LIBRARY v10 | Dispatch card inherits mandatory preflight (task-id-guard.sh) and validation-scope expansion from v10. | No change to v10. Dispatch card references v10 requirements. |
| BFPS v12 | BFPS remains the ingestion/handoff artifact. CURRENT_CONDITIONS.md complements BFPS by providing live runtime state rather than session-start snapshot. | No change to BFPS v12. |
| AGENT_CONTRACT | Unaffected. Cecil tool-use and confirmation rules unchanged. | No change. |
| RUNBOOK | Unaffected. Session-start protocol, lane definitions unchanged. | No change. |
| MERGE_GATE | Unaffected. Merge checklist unchanged. | No change. |

## 6. Acceptance Criteria for Phase 1

Phase 1 is successful when ALL of the following are true:

1. All three spec files exist and are internally consistent.
2. `docs/dev/CURRENT_CONDITIONS.md` exists with the defined schema.
3. ChatGPT dispatch operating card exists as a GPT project file.
4. At least 3 real Codex dispatches have been framed using the new standard.
5. Codex reception checklist has been applied to at least 3 incoming dispatches.
6. CURRENT_CONDITIONS.md has been updated at least 3 times during real operations.
7. No existing canonical files have been modified.
8. Greg has reviewed pilot results and confirmed whether to proceed to Phase 2.

## 7. Open Decisions

7.1. **Hot-file list for CURRENT_CONDITIONS.md.** Should CURRENT_CONDITIONS.md be added to the hot-file list? Recommendation: NO at Phase 1. It is a high-write file by design. Adding it to the hot-file list would create friction. Revisit if merge conflicts become a problem.

7.2. **GPT project file update cadence.** When the canonical repo spec changes, how quickly must the GPT project file copy be updated? Recommendation: ChatGPT updates the project file copy at next session start after any spec change.

## 8. Recommended Next Steps After Planning

1. Greg reviews this plan and the three specs.
2. Greg decides any remaining open decisions.
3. Implementation task: create `docs/dev/CURRENT_CONDITIONS.md` with initial schema.
4. Implementation task: copy dispatch operating card to GPT project file.
5. Pilot: 3–5 dispatches using the new standard.
6. Evaluation: Greg and ChatGPT assess Phase 1 against acceptance criteria.
7. If successful: proceed to Phase 2 planning (investigation mode, report formats, landing zone).

## 9. Clean Boundary Between Phase 1 and Phase 2

Phase 1 ends when the dispatch standard, shared store, and reception checklist are operational and piloted.

Phase 2 begins with:
- Codex investigation mode as an explicit dispatch type
- Non-code output landing zone (`docs/dev/analysis/`)
- Standardized report format reference document
- Report format adoption across completion packets and investigation reports

Phase 2 MUST NOT begin until Phase 1 acceptance criteria (Section 6) are met.
