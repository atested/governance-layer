# Briefing Format Packet Specification (BFPS) v13

Version: v13
Purpose: Standardize handoff briefings between chats in Claude.ai Projects for governance layer operations

## 1. Required sections (in order)

Every briefing MUST include these sections in this exact order:

### 1.1 Header
```
Briefing for [Chat Name/ID]
Created: [ISO timestamp]
BFPS Version: v13
```

### 1.2 Repo path and execution root gate
```
Repo path: /Volumes/SSD/archive/gov/governance-layer
WRONG_EXECUTION_ROOT gate: FAIL if pwd != repo path at start
```

### 1.3 Origin/main SHA at briefing creation
```
origin/main SHA: <40-char hex SHA>
```
If unknown at briefing creation time, write: "resolved at runtime"

### 1.4 Hot files list
List all files that MUST NOT be touched except under specific authorized conditions:
```
Hot files (MUST NOT TOUCH unless explicitly authorized):
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/codex-unattended.sh [shelved]
- docs/dev/WORK_QUEUE.md
- docs/dev/ASSIGNMENTS.md (Cecil edits only during merge finalization)
```

### 1.5 Files that govern behavior

#### Dispatch format

**Formal dispatch and results format:**
- Source: `docs/dev/OPS_PROCESS__DISPATCH_CECIL__v2.md` §9
- All dispatches from Tier 0 to Cecil MUST follow the formal dispatch format defined in §9
- Results from Cecil MUST follow the formal results format defined in §9

**Cecil dispatch library [historical]:**
- Source: `docs/dev/DISPATCH_LIBRARY__CECIL_CODEX__CANON.md`
- Resolves to: `DISPATCH_LIBRARY__CECIL_CODEX__v10.md`
- Status: Historical reference. Predates the formal dispatch format in OPS_PROCESS v2 §9. The dispatch library contains useful preflight contracts and sensitive-surface definitions that remain applicable. Tier 0 may reference it when constructing dispatches that touch sensitive surfaces.

**Codex batch dispatch templates [shelved]:**
- Source: `docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md` section 9.1
- Status: Shelved. Codex is not active. Retained as historical reference.

**Codex preferred shape addendum [shelved]:**
- The combined-workfront dispatch shape (WORKFRONT_TYPE, TARGET_SURFACE, EXECUTION_ROOT, HARD_GATE, BASELINE, PRIMARY_OBJECTIVE, bounded control sections, execution traceability sections) was designed for Codex dispatches.
- Status: Shelved. Codex is not active. Retained as historical reference. Some structural patterns may inform Tier 0 dispatch construction.

#### Governing files

| File | Path | Purpose |
|---|---|---|
| Operations process (current) | `docs/dev/OPS_PROCESS__DISPATCH_CECIL__v2.md` | Dispatch architecture, roles, merge strategy, constraints |
| Operations process (historical) | `docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md` | Historical reference only |
| OPS canonical record | `docs/dev/OPS_CANONICAL.md` | Canonical ops record, lanes, invariants, script registry |
| Agents | `AGENTS.md` | Agent roles and responsibilities |
| Merge policy | `docs/dev/MERGE_GATE.md` | Merge requirements and verification rules |
| Task specification format | `docs/dev/TASK_TEMPLATE.md` | Standard task specification template |
| Evidence contract | `docs/dev/EVIDENCE-CONTRACT.md` | Evidence bundle specification |
| Claude.ai Project setup | `docs/dev/CLAUDE_AI_PROJECT_SETUP__v1.md` | Procedure for bootstrapping and maintaining Claude.ai Projects |

### 1.6 Current state

Facts-only summary of the repo state at briefing creation:

```
Current state:
- origin/main HEAD: [SHA if known]
- Major capabilities merged: [list]
- Active work in progress: [list]
- Known blockers: [list or "none"]
```

### 1.7 Active objective for this chat

1-3 bullets explicitly describing what the next chat session should work on:

```
Active objective for this chat:
- [Objective 1]
- [Objective 2]
- [Objective 3 if applicable]
```

### 1.8 STOP packet pointer

```
STOP conditions for all dispatches:
- See: docs/dev/OPS_PROCESS__DISPATCH_CECIL__v2.md §10 (system-wide constraints)
- Preservation invariant: no out-of-scope modifications (§10.1)
- Fail-closed on missing specs or allowlists
- Fail-closed on hot file violations (unless explicitly authorized)
- Fail-closed on ASSIGNMENTS.md conflicts outside union rule
```

### 1.9 Next chat creation protocol

When Greg says "Create the handoff briefing for the next chat":

1. **Refresh current state (required)**:
   - Read `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md` for canonical capability state
   - Read `docs/dev/WORK_QUEUE.md` for authoritative workfront state
   - Read current implementation-plan docs and corresponding ready-task docs for active initiatives
   - If capability state and workfront state diverge, state the divergence explicitly
   - If authoritative workfront state cannot be determined cleanly from repo-readable sources, STOP before briefing creation
2. **Create the briefing**:
   - Use BFPS v13 required section order exactly
   - Populate all sections from current repo state and chat context
3. **Populate origin/main SHA**: Use the current known HEAD if available; otherwise write "resolved at runtime"
4. **Keep repo path mapping + WRONG_EXECUTION_ROOT gate**: Copy exactly from section 1.2
5. **Include hot files list**: Copy exactly from section 1.4
6. **Include governing files**: Copy the table from section 1.5
7. **Include compact "Current state" block**:
   - Facts only
   - Latest merged HEAD
   - Major merged capabilities since last briefing
   - Active work in progress
   - Known blockers
8. **Include "Active objective for this chat"**:
   - 1-3 bullets
   - Explicitly tied to the next work Greg has identified
   - No speculation or invented objectives
9. **Include capability map startup reference block**:
   - Include required fields from section 1.10
   - Ensure current judgment summary is populated
10. **Include Current Planning State section**:
    - Include required fields from section 1.11
    - Ensure it is derived from `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`
11. **Include Authoritative Workfront Inputs section**:
    - Include required fields from section 1.12

**Greg uploads the briefing** to the Claude.ai Project per `CLAUDE_AI_PROJECT_SETUP__v1.md` §4. The next chat reads it at start.

**Prohibited actions:**
- Do NOT add commentary or "helpful suggestions" to the briefing structure
- Do NOT deviate from BFPS v13 required section order
- Do NOT generate a briefing from stale prior briefing text or assistant reconstruction — always refresh from repo state first

### 1.10 Capability map startup reference (required)

Every briefing MUST include this compact planning block:

```
Capability map reference:
- Path: docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- Canonical GitHub link: https://github.com/GregKeeter/governance-layer/blob/main/docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- Purpose: canonical current-main planning state for next-workfront selection
- Required startup use: read before proposing or dispatching a new workfront
- Fail-closed rule: if the capability map path or canonical link is unreadable, STOP before workfront selection
- Lightweight maintenance rule: update map state after every Cecil merge window
- Deeper refresh trigger: only when judgment state is EXHAUSTED, STALE, or INSUFFICIENT
- Current judgment summary: [VALID | PARTIALLY_CONSUMED | EXHAUSTED | STALE | INSUFFICIENT]
```

### 1.11 Current Planning State (required, map-derived)

Every briefing MUST include this section derived from `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`:

```
Current Planning State:
- Current baseline: <origin/main SHA>
- Latest merge window: <Mx / merge commit>
- Latest landed tasks: <TASK list>
- Planning judgment state: <VALID | PARTIALLY_CONSUMED | EXHAUSTED | STALE | INSUFFICIENT>
- Live surfaces summary: <compact list>
- Preferred next lane: <one lane>
- Secondary candidates: <1..3 lanes>
- Major constraints / sensitive areas: <compact list>
- Refresh marker: <map reflects current main = yes/no + source SHA>
- Refresh / new-chat trigger note: <trigger conditions>
```

Rule:
- This section is a session-useful extracted subset, not a duplicate of the full capability map.
- The extracted subset must reflect both capability-state and authoritative-workfront-state inputs from the refresh step.
- If those two truth classes diverge, briefing inputs must state the divergence explicitly rather than silently defaulting to one source.

### 1.12 Authoritative Workfront Inputs (required for refresh workflows)

Every pre-briefing refresh MUST inspect both truth classes:

1. Capability state:
   - `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`
2. Authoritative workfront state on main:
   - `docs/dev/WORK_QUEUE.md`
   - current canonical implementation-plan docs for the active initiative
   - corresponding `docs/dev/tasks/ready/` task specs for that initiative

The specific source instance depends on the currently active initiative. Tier 0 identifies the active initiative from `docs/dev/WORK_QUEUE.md` and reads the corresponding implementation-plan and ready-task docs.

Fail-closed rule: if the workfront source docs for the active initiative are unreadable or missing, STOP before briefing creation and flag the gap.

## 2. Versioning policy

BFPS version increments when:
- Required sections change
- Section ordering changes
- Canonical file pointers change
- Next chat creation protocol changes

Patch notes for v13:
- Updated for dispatch architecture (OPS_PROCESS v2). Tier 0 replaces ChatGPT as orchestrator throughout.
- §1.1: Removed `DEV<N>` numbering from header format. Chat identity is now freeform.
- §1.4: Annotated `codex-unattended.sh` as [shelved].
- §1.5: Restructured. Formal dispatch format now defined in OPS_PROCESS v2 §9. Cecil dispatch library reclassified as historical reference. Codex batch dispatch templates and preferred shape addendum marked [shelved]. Added governing files table with OPS_PROCESS v2, OPS_CANONICAL, AGENTS.md, and CLAUDE_AI_PROJECT_SETUP__v1.md.
- §1.8: STOP pointer updated from OPS_PROCESS v1 §6 to OPS_PROCESS v2 §10 (system-wide constraints). Added preservation invariant reference.
- §1.9: Rewritten. Removed Codex refresh-then-brief workflow (Codex is shelved). Refresh is now a direct read of repo state by Tier 0. Removed DEV-number prompting (freeform chat identity). Removed requirement for Greg to paste dispatch templates. Added upload step per CLAUDE_AI_PROJECT_SETUP__v1.md.
- §1.12: Removed hardcoded RDD initiative source instance. Active initiative is now determined dynamically from WORK_QUEUE.md by Tier 0.
- §3: Compliance verification updated to match v13 sections.

Prior version: BFPS v12 (`docs/dev/BRIEFING_FORMAT__BFPS_v12.md`, preserved unchanged).

## 3. Compliance verification

A briefing is BFPS v13 compliant if and only if:
1. All required sections present in exact order (§1.1 through §1.12)
2. All section content follows the format specified above
3. No extra sections inserted between required sections
4. Dispatch format references OPS_PROCESS v2 §9 as authoritative
5. Governing files table includes all entries from §1.5
6. Capability map startup reference block is present with path, canonical link, startup-use rule, fail-closed unreadable rule, maintenance rule, refresh trigger, and current judgment summary
7. Current Planning State section is present and map-derived with all required fields from §1.11
8. Refresh workflow uses direct repo-state reads (not Codex dispatch)
9. Refresh workflows include mandatory authoritative-workfront-source inspection (§1.12) alongside capability-state inspection
10. Divergence between capability-state and authoritative-workfront-state inputs is surfaced explicitly or fails closed if unresolved

Non-compliant briefings MUST be regenerated before chat handoff.
