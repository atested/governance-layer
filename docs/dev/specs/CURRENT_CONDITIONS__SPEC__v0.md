# Current Conditions Store Specification

Version: v0 (planning draft)
Status: Phase 1 specification — not yet operational
Location: `docs/dev/CURRENT_CONDITIONS.md`

## 1. Purpose

1.1. CURRENT_CONDITIONS.md is the single shared source of current runtime state for all agents in the multi-agent operating model.

1.2. It answers: "What is the state of the system right now?"

1.3. It is designed for rapid consultation during:
- dispatch preparation (ChatGPT reads before framing Codex work)
- execution context loading (Codex reads at dispatch start)
- merge review (Cecil reads before merge execution)

## 2. Schema

The file MUST use the following exact schema. Sections MUST appear in this order.

```markdown
# Current Conditions
Updated: [ISO timestamp] by [writer identity]

## Main
SHA: [40-char hex SHA of origin/main HEAD]

## In-Flight
| Branch | Task | Executor | Status | Key Files |
|--------|------|----------|--------|-----------|
| [branch name] | [task ID] | [executor] | [status] | [comma-separated key files] |

## Last Merge
Task: [task ID] | Branch: [branch name] | Result: [MERGED / REJECTED] | Date: [ISO date]

## Merge Quality
[Most recent Cecil merge-quality feedback, 1-3 lines, or "CLEAN"]

## Blockers
[Active STOP conditions, blockers, or "None"]

## Last Dispatch
Mode: [Execute / Investigate] | Task: [task ID] | To: [executor] | Status: [pending / complete / failed]
```

### 2.1. Field Definitions

| Field | Meaning | Required |
|---|---|---|
| Updated | ISO timestamp and writer identity of last update | YES |
| Main SHA | Current origin/main HEAD SHA | YES |
| In-Flight table | All branches currently in progress or awaiting merge | YES (may be empty table) |
| In-Flight Status | One of: in-progress, complete, awaiting-merge, blocked | YES per row |
| Last Merge | Most recent merge attempt, regardless of outcome | YES |
| Merge Quality | Most recent Cecil feedback from post-merge report Section 4, or "CLEAN" | YES |
| Blockers | Active conditions preventing work, or "None" | YES |
| Last Dispatch | Most recent Codex-facing dispatch | YES |

## 3. Ownership Model

### 3.1. Logical Authority vs Mechanical Writer

3.1.1. ChatGPT is the primary **logical state authority** for CURRENT_CONDITIONS.md. ChatGPT determines what the current conditions are and what updates are needed.

3.1.2. ChatGPT cannot write to the repo directly. Only repo-capable agents (Codex and Cecil) perform actual file writes to CURRENT_CONDITIONS.md.

3.1.3. **State-change reality rule:** A CURRENT_CONDITIONS change is not real until a repo-capable agent has written it to the file. ChatGPT MUST NOT assume CURRENT_CONDITIONS.md reflects a state change until a repo-capable agent has confirmed the write.

### 3.2. Section Ownership

Each section has a designated logical authority (who determines the correct value) and mechanical writer (who performs the repo write).

| Section | Logical Authority | Mechanical Writer |
|---------|-------------------|-------------------|
| Updated | Writer of current update | Codex or Cecil (whoever is performing the write) |
| Main SHA | Cecil (authoritative after merge) / ChatGPT (after independent verification) | Cecil (post-merge) / Codex (when directed by ChatGPT) |
| In-Flight | ChatGPT (overall table) / Codex (own branch status) | Codex (during execution) / Codex (when directed by ChatGPT) |
| Last Merge | Cecil (authoritative) | Cecil |
| Merge Quality | Cecil (authoritative) | Cecil |
| Blockers | ChatGPT (primary) / any agent discovering a blocker | Codex or Cecil (whoever is performing the write) |
| Last Dispatch | ChatGPT (authoritative) | Codex (when directed by ChatGPT) |

### 3.3. Section Protection

An agent MUST NOT write to a section for which it is not listed as a mechanical writer in Section 3.2, unless explicitly directed by the section's logical authority in a dispatch or merge instruction.

### 3.4. Sisters / QT

Sisters and QT MUST NOT write to CURRENT_CONDITIONS.md under any circumstances.

## 4. Read Rules

4.1. All agents (ChatGPT, Codex, Cecil, sisters) MAY read CURRENT_CONDITIONS.md at any time.

4.2. ChatGPT reads CURRENT_CONDITIONS.md via one of:
- Requesting a Codex read operation.
- Greg-provided paste of the file contents.

4.3. ChatGPT SHOULD read the file before preparing any Codex dispatch, specifically to:
- check In-Flight table for file-overlap with proposed work (batch coherence)
- check Blockers for active STOP conditions
- check Main SHA for baseline currency

4.4. Cecil SHOULD read the file before merge execution to verify current branch state.

4.5. Codex SHOULD read the file at dispatch start for context loading.

## 5. Update Rules

5.1. ChatGPT MUST include CURRENT_CONDITIONS update instructions in a Codex dispatch when any ChatGPT-authoritative section needs to change. The dispatch MUST specify the exact section(s) to update and the new value(s).

5.2. Codex MUST apply CURRENT_CONDITIONS update instructions included in a dispatch. This is mechanical: Codex writes the values ChatGPT specifies, without inferring or modifying them.

5.3. Cecil MUST update the Last Merge, Merge Quality, and Main SHA sections after every merge completion. These updates are Cecil-authoritative and do not require ChatGPT instruction.

5.4. Codex SHOULD update its own In-Flight branch status when that status changes during execution (e.g., in-progress → complete). This is a governed self-update within Codex's designated section.

5.5. The Updated field MUST be refreshed on every write, regardless of which agent performs it.

5.6. ChatGPT MUST include update instructions after each of:
- dispatching work to Codex (update Last Dispatch, In-Flight table)
- receiving a Codex completion result (update In-Flight table)
- learning of a new blocker or blocker resolution (update Blockers)

## 6. Staleness Handling

6.1. If the Updated timestamp is more than 24 hours old, any agent reading the file SHOULD treat its contents as potentially stale.

6.2. A stale file MUST NOT be used as the sole basis for batch coherence checks. ChatGPT MUST verify In-Flight state through other means (git branch inspection, Greg confirmation) before relying on a stale file.

## 7. Overwrite versus Append Behavior

7.1. The file is overwritten per-section, not appended. Each section reflects current state only.

7.2. The In-Flight table is fully replaced on each ChatGPT update. Rows for completed and merged branches are removed.

7.3. There is no historical retention in this file. History lives in WORK_QUEUE.md, ASSIGNMENTS.md, and git log.

## 8. What MUST NOT Live in This File

1. Task specifications or task detail
2. BFPS content or session handoff information
3. Historical records beyond the most recent cycle
4. Evidence bundles, proof packets, or test results
5. Architectural decisions or design documents
6. Planning documents, roadmaps, or capability maps
7. Dispatch content (the file records that a dispatch occurred, not the dispatch itself)
8. Merge conflict details (those belong in merge reports)

## 9. Interaction with Existing Artifacts

| Artifact | Relationship |
|---|---|
| BFPS v12 | BFPS is a session-start snapshot for onboarding. CURRENT_CONDITIONS is live runtime state. They serve different purposes. BFPS section 1.6 ("Current state") covers similar ground but is static at briefing time. CURRENT_CONDITIONS is continuously updated. |
| WORK_QUEUE.md | CURRENT_CONDITIONS references active task IDs. WORK_QUEUE.md holds full task lifecycle history. |
| ASSIGNMENTS.md | CURRENT_CONDITIONS references assigned executor. ASSIGNMENTS.md is authoritative for ownership. |
| Merge reports | CURRENT_CONDITIONS holds Last Merge summary. Full merge detail lives in merge reports and git log. |
| Task files | CURRENT_CONDITIONS does not hold specs. It holds status pointers to active tasks. |
| CURRENT_MAIN_CAPABILITY_MAP.md | CURRENT_CONDITIONS tracks runtime operational state. The capability map tracks planning and capability state. They are complementary. |
