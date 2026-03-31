# Claude.ai Project Setup Procedure v1

**Status:** Canonical procedure for bootstrapping and maintaining Claude.ai Projects used by Tier 0.
**Scope:** Claude.ai Project creation, file export, project instructions, BFPS briefing lifecycle, and file currency.

## 1. Export file set

All files below must be exported from the governance-layer repo to `~/transport/exports/` before creating a new Claude.ai Project, and kept current thereafter.

### 1.1 Governance files (stable)

These change infrequently. Update when a dispatch modifies them.

| File | Source path | Purpose |
|---|---|---|
| BFPS template | `docs/dev/BRIEFING_FORMAT__BFPS_v13.md` | Briefing format for chat handoffs |
| OPS_PROCESS v2 | `docs/dev/OPS_PROCESS__DISPATCH_CECIL__v2.md` | Governing ops document |
| AGENTS | `AGENTS.md` | Agent roles and quick reference |
| OPS_CANONICAL | `docs/dev/OPS_CANONICAL.md` | Canonical ops record, lanes, invariants |
| Merge policy | `docs/dev/MERGE_GATE.md` | Merge requirements — Tier 0 references when constructing merge dispatches |

### 1.2 State files (dynamic)

These change after merge windows and workfront transitions. Re-export after every Cecil merge and before every new Claude.ai chat.

| File | Source path | Purpose |
|---|---|---|
| Capability map | `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md` | Required by BFPS v13 §1.10, §1.11 for planning state |
| Work queue | `docs/dev/WORK_QUEUE.md` | Required by BFPS v13 §1.12 for workfront inputs |

### 1.3 Export command (Cecil executes)

```bash
cp docs/dev/BRIEFING_FORMAT__BFPS_v13.md \
   docs/dev/OPS_PROCESS__DISPATCH_CECIL__v2.md \
   AGENTS.md \
   docs/dev/OPS_CANONICAL.md \
   docs/dev/MERGE_GATE.md \
   docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md \
   docs/dev/WORK_QUEUE.md \
   ~/transport/exports/
```

If the file set changes (files added or removed), update the tables above and this command.

### 1.4 Files NOT in the export set

These files are referenced by BFPS v13 but are not exported because they are Cecil-side artifacts or dynamic per-initiative:

| File | Reason not exported |
|---|---|
| `docs/dev/TASK_TEMPLATE.md` | Cecil uses for task creation, not needed by Tier 0 |
| `docs/dev/EVIDENCE-CONTRACT.md` | Cecil uses for evidence bundles, not needed by Tier 0 |
| `docs/dev/DISPATCH_LIBRARY__CECIL_CODEX__CANON.md` | Historical reference. Tier 0 may request Cecil to consult it in dispatches. |
| Implementation-plan docs | Dynamic per initiative. Tier 0 identifies the active initiative from WORK_QUEUE.md and requests specific docs from Cecil if needed. |
| Ready-task docs (`docs/dev/tasks/ready/`) | Dynamic per initiative. Same as above. |

## 2. Creating the Claude.ai Project

Greg performs these steps:

1. Open Claude.ai → Projects → Create Project
2. Name the project (e.g., "Governance Layer — Tier 0")
3. Upload all files from `~/transport/exports/` to the project's knowledge files
4. Paste the standard project instructions from section 3 into the project's custom instructions field
5. Create the first chat in the project

## 3. Standard project instructions

Paste the following verbatim into the Claude.ai Project custom instructions:

---

You are Tier 0: the strategic orchestrator for the governance-layer project.

**Your role (from AGENTS.md):**
- Produce formal dispatches for Cecil (the builder)
- Review results returned by Cecil
- Never write code or execute tasks directly

**Governing documents (uploaded to this project):**
- OPS_PROCESS__DISPATCH_CECIL__v2.md — the complete ops process
- OPS_CANONICAL.md — canonical ops record, lanes, invariants
- AGENTS.md — agent roles and responsibilities
- BRIEFING_FORMAT__BFPS_v13.md — briefing format specification
- MERGE_GATE.md — merge requirements (reference when constructing merge dispatches)

**State files (uploaded to this project, refreshed frequently):**
- CURRENT_MAIN_CAPABILITY_MAP.md — canonical planning state for workfront selection
- WORK_QUEUE.md — authoritative workfront state

**Dispatch format:** Follow §9 of OPS_PROCESS v2 for dispatch and results format.

**Briefing lifecycle:** Every chat in this project ends by producing a BFPS briefing (per BRIEFING_FORMAT__BFPS_v13.md). Greg uploads the briefing to this project before starting the next chat. Read the most recent briefing at the start of each chat to establish continuity.

**State file refresh:** Before creating a briefing, check whether CURRENT_MAIN_CAPABILITY_MAP.md and WORK_QUEUE.md are current. If a merge has landed since they were last uploaded, ask Greg to have Cecil re-export and upload the updated files before proceeding with briefing creation.

**Constraints:**
- You produce dispatches; Cecil executes them
- You review results; Cecil merges to main
- You do not write code, run commands, or make direct changes
- All dispatches must follow the formal format in OPS_PROCESS v2 §9
- Respect the preservation invariant (OPS_PROCESS v2 §10.1)
- Include stage-forward advisory expectations in dispatches where appropriate

---

## 4. BFPS briefing lifecycle

Each chat in a Claude.ai Project follows this cycle:

1. **Start of chat:** Read the most recent BFPS briefing uploaded to the project. This establishes where the previous chat left off — active work, pending dispatches, observations, and advisories.

2. **During the chat:** Tier 0 and Greg work together — planning, producing dispatches, reviewing results, making decisions.

3. **End of chat:** Before closing, produce a BFPS briefing following `BRIEFING_FORMAT__BFPS_v13.md`. The briefing captures:
   - Current state of all active work
   - Pending dispatches and their status
   - Results received and reviewed
   - Open questions or decisions
   - Stage-forward advisories for the next chat

4. **Between chats:** Greg downloads or copies the briefing and uploads it to the Claude.ai Project's knowledge files, replacing or supplementing the previous briefing.

5. **Next chat:** The new chat reads the briefing at start, establishing continuity.

This cycle ensures no context is lost between chats. The BFPS briefing is the sole handoff mechanism — there is no other state transfer between Claude.ai chats.

## 5. Keeping project files current

### 5.1 Governance files (stable)

**Trigger:** Any dispatch whose scope includes modification of a governance file listed in §1.1.

**Process:**
1. Cecil copies updated files to `~/transport/exports/` using the export command from §1.3
2. Cecil notifies Greg in the results file: "Governance files updated in `~/transport/exports/`. Upload the updated files to the Claude.ai Project."

This is a standing obligation — Cecil adds the export step without needing explicit instruction.

### 5.2 State files (dynamic)

**Trigger:** Every Cecil merge to main, and before every new Claude.ai chat.

**Process:**
1. After a merge, Cecil re-exports state files: `cp docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md docs/dev/WORK_QUEUE.md ~/transport/exports/`
2. Cecil notifies Greg: "State files updated in `~/transport/exports/`. Upload before starting the next Claude.ai chat."
3. Greg uploads the updated state files to the Claude.ai Project before creating a new chat.

If Greg starts a new chat without refreshing state files, Tier 0 should detect staleness (SHA mismatch between briefing's origin/main and the state files) and ask Greg to refresh before proceeding with briefing creation.

## 6. Adding new shared files

If a new file should be added to the export set:

1. Add it to the appropriate table in §1.1 (governance) or §1.2 (state)
2. Update the export command in §1.3
3. Update the standard project instructions in §3 if the file should be listed there
4. Copy it to `~/transport/exports/`
5. Notify Greg to upload it to all active Claude.ai Projects

## Revision history

- 2026-03-28: Added dynamic state files (CURRENT_MAIN_CAPABILITY_MAP.md, WORK_QUEUE.md) and MERGE_GATE.md to export set. Split §1 into governance files and state files with distinct update cadences. Updated §3 standard project instructions. Added §5.2 dynamic state file refresh process. Documented files NOT in export set with rationale. (D-2026-0328-005)
- 2026-03-28: Initial version (D-2026-0328-003)
