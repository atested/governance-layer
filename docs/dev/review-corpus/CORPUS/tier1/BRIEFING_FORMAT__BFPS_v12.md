# Briefing Format Packet Specification (BFPS) v12

Version: v12
Purpose: Standardize handoff briefings between DevN chats for governance layer operations

## 1. Required sections (in order)

Every DevN briefing MUST include these sections in this exact order:

### 1.1 Header
```
DEV<N> Briefing for [Chat Name/ID]
Created: [ISO timestamp]
BFPS Version: v12
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
- system/scripts/codex-unattended.sh
- docs/dev/WORK_QUEUE.md
- docs/dev/ASSIGNMENTS.md (Cecil edits only during merge finalization)
```

### 1.5 Files that govern behavior

#### Canonical dispatch pointers

**Cecil merge dispatch templates:**
- Source: `docs/dev/DISPATCH_LIBRARY__CECIL_CODEX__CANON.md`
- All Cecil merge window dispatches MUST be copied from this file
- Version seam rule: BFPS references the `__CANON` path; the CANON file resolves the active versioned dispatch library (currently `DISPATCH_LIBRARY__CECIL_CODEX__v10.md`)

**Codex batch dispatch template requirements:**
- Source: `docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md` section 9.1
- All Codex batch dispatches MUST follow the requirements specified in section 9.1

**Preferred shape addendum for qualifying current-main combined workfronts (Codex):**
- Include, in order: `WORKFRONT_TYPE`, `TARGET_SURFACE`, `EXECUTION_ROOT`, `HARD_GATE`, `BASELINE`, and `PRIMARY_OBJECTIVE`.
- Require bounded control sections: `ALLOWED_WRITES`, `DO_NOT_TOUCH`, `AUTHORIZED_CONTINUATIONS`, `FORBIDDEN_EXPANSIONS`, and `STOP_BOUNDARIES`.
- Require execution traceability sections: `REQUIRED_EVIDENCE_OUTPUTS`, `COMPLETION_PACKET`, and `FAIL_CLOSED`.
- For combined restock+implementation lanes, explicitly require spec creation first, verification that specs exist on branch tip, then implementation/validation/publish.
- Keep this as structure guidance only; do not duplicate full dispatch templates inside BFPS.

**Note:** The Cecil dispatch library is governed through the CANON pointer; Codex dispatch requirements remain authoritative in OPS_PROCESS v1 section 9.1.

#### Other governing files
- Merge policy: `docs/dev/MERGE_GATE.md`
- Task specification format: `docs/dev/TASK_TEMPLATE.md`
- Evidence contract: `docs/dev/EVIDENCE-CONTRACT.md`
- Operations process: `docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md`

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
- See: docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md section 6
- Fail-closed on missing specs or allowlists
- Fail-closed on hot file violations (unless explicitly authorized)
- Fail-closed on ASSIGNMENTS.md conflicts outside union rule
```

### 1.9 Next chat creation protocol

When Greg says "Create the handoff briefing for the next chat":

1. **Start refresh-then-brief workflow (required)**:
   - Briefing creation MUST start with a Codex task to refresh/update `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`.
   - After Codex refresh completes, provide the Cecil merge block to land refreshed map state on main.
   - Do NOT create the new briefing before refresh + merge completion.
   - Refresh scope is mandatory dual-source:
     - canonical capability state (`docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`)
     - canonical authoritative workfront state on main (`docs/dev/WORK_QUEUE.md`, active implementation-plan docs, and corresponding ready-task docs)
   - If authoritative workfront state cannot be determined cleanly from repo-readable sources, STOP before briefing creation.
2. **Prompt Dev number before briefing creation**:
   - Propose next expected value using this format: `Ready to create the briefing using DEV<N>?`
   - If Greg says `yes`, use the proposed DEV number.
   - If Greg specifies a different number, use Greg's number.
3. **Increment session**: Dev<N> → Dev<N+1>
   - Briefing identity/title must use `DEV<N>` format.
4. **Use BFPS v12 required section order**: Copy the exact structure from this specification
5. **Populate origin/main SHA**: Use the current known HEAD if Greg provides it; otherwise write "resolved at runtime"
6. **Keep repo path mapping + WRONG_EXECUTION_ROOT gate**: Copy exactly from section 1.2
7. **Include hot files list**: Copy exactly from section 1.4
8. **Include canonical dispatch pointers**:
   - Cecil merge templates from DISPATCH_LIBRARY__CECIL_CODEX__CANON.md
   - Codex template requirements from OPS_PROCESS v1 section 9.1
   - Include the preferred combined-workfront dispatch-shape addendum from section 1.5 when applicable
9. **Include compact "Current state" block**:
   - Facts only
   - Latest merged HEAD
   - Major merged capabilities since last briefing
   - Active work in progress
   - Known blockers
10. **Include "Active objective for this chat"**:
   - 1-3 bullets
   - Explicitly tied to the next work Greg has requested
   - No speculation or invented objectives
11. **Include capability map startup reference block**:
   - Include required fields from section 1.10
   - Ensure current judgment summary is populated
12. **Include Current Planning State section**:
   - Include required fields from section 1.11
   - Ensure it is derived from `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`
13. **Session continuation rule**:
   - Within the same chat, update local session planning state after merges and continue selecting lanes while judgment remains coherent
   - Trigger new chat when judgment becomes `EXHAUSTED`, `STALE`, or `INSUFFICIENT`, or when the chat becomes flaky enough to reduce trust

**Prohibited actions:**
- Do NOT ask Greg to paste dispatch templates (unless the referenced files are actually missing from the repo)
- Do NOT add commentary or "helpful suggestions" to the briefing structure
- Do NOT deviate from BFPS v12 required section order
- Do NOT generate a new Dev briefing directly from in-chat memory, stale prior briefing text, or assistant reconstruction

### 1.10 Capability map startup reference (required)

Every new Dev briefing MUST include this compact planning block:

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

Every new Dev briefing MUST include this section derived from `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`:

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

Every pre-briefing refresh / project-state refresh MUST inspect both truth classes:

1. Capability state:
   - `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`
2. Authoritative workfront state on main:
   - `docs/dev/WORK_QUEUE.md`
   - current canonical implementation-plan docs for the active initiative
   - corresponding `docs/dev/tasks/ready/` task specs for that initiative

Current required source instance for the active RDD initiative:
- `docs/dev/WORK_QUEUE.md`
- `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`
- doctrine source path for this initiative:
  - expected legacy path: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE.md`
  - current canonical path on main: `docs/RESIDUAL_DISCRETION_DOCTRINE.md`
  - fail-closed rule: if neither path is readable, STOP
- `docs/dev/tasks/ready/TASK_311__rdd_pass_v02_schema_fields.md`
- `docs/dev/tasks/ready/TASK_312__rdd_pass_undecided_emission.md`
- `docs/dev/tasks/ready/TASK_313__rdd_pass_undecided_test_coverage.md`

## 2. Versioning policy

BFPS version increments when:
- Required sections change
- Section ordering changes
- Canonical file pointers change
- Next chat creation protocol changes

Patch notes for v12:
- Fixed canonical dispatch pointer handling by routing BFPS through DISPATCH_LIBRARY__CECIL_CODEX__CANON.md (version resolved by CANON) and OPS_PROCESS v1 section 9.1 (Codex)
- Added "Next chat creation protocol" as required section 1.9
- Made "canonical template missing" failure impossible by explicitly documenting authoritative sources

## 3. Compliance verification

A `DEV<N>` briefing is BFPS v12 compliant if and only if:
1. All required sections present in exact order
2. All section content follows the format specified above
3. No extra sections inserted between required sections
4. Canonical dispatch pointers reference correct files (DISPATCH_LIBRARY__CECIL_CODEX__CANON.md for Cecil, OPS_PROCESS v1 §9.1 for Codex)
5. Capability map startup reference block is present with path, canonical link, startup-use rule, fail-closed unreadable rule, maintenance rule, refresh trigger, and current judgment summary
6. Current Planning State section is present and map-derived with all required fields from section 1.11
7. Pre-briefing DEV-number prompt rule is present and explicit
8. Refresh-then-brief workflow rule is present and explicit (Codex refresh -> Cecil merge -> DEV prompt -> briefing generation)
9. Refresh workflows include mandatory authoritative-workfront-source inspection (section 1.12) alongside capability-state inspection
10. Divergence between capability-state and authoritative-workfront-state inputs is surfaced explicitly or fails closed if unresolved

Non-compliant briefings MUST be regenerated before chat handoff.
