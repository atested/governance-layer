# Ingestion Workflow

Process documentation for converting chat-derived ideas and discussions into canonical repository documentation.

---

## Purpose

This workflow ensures that valuable concepts, design decisions, and architectural principles discussed in chat sessions are systematically canonicalized in the repository. It prevents knowledge loss and maintains documentation coherence.

---

## Status Tags

All ingested content must be tagged with one of these status markers:

| Tag | Meaning | Criteria |
|---|---|---|
| `[IMPLEMENTED]` | Code exists, tested, evidence on main | Tests pass, evidence bundle committed, merged to main |
| `[IN_PROGRESS]` | Active development, branch exists or task in queue | Branch on origin, or task in WORK_QUEUE.md Next section |
| `[DESIGN_ONLY]` | Spec/EPIC exists, no implementation yet | EPIC_*.md or detailed spec committed, no code |
| `[SPECULATIVE]` | Idea/proposal only, no spec or code | Concept discussed, not formally specified |
| `[NEEDS_VALIDATION]` | Implementation exists but needs verification | Code committed but tests incomplete or failing |

**Tag placement**: Include tag immediately after section heading or item description.

**Example**:
```markdown
### Ed25519 Signing `[DESIGN_ONLY]`
**Description**: Cryptographic signatures over policy records for non-repudiation.
```

---

## Five-Step Ingestion Process

### Step 1: Capture (During Conversation)

**When to capture**: Identify content that should be canonical:
- **Architectural principles**: "Cecil is sole merger to main", "Policy evaluation is deterministic"
- **Technical guarantees**: "Same inputs → same record hash", "Fail-closed on errors"
- **Application concepts**: "Case Strength uses attestation chains", "Time ribbon renders decision DAGs"
- **Design decisions**: "ASSIGNMENTS.md uses UNION rule", "EVIDENCE_ONLY branches held by default"
- **Workflow protocols**: "Morning merge routine", "No-ff merge strategy"

**Mark in conversation**: When Cecil identifies canonical content, note target doc:
```
"This should be canonical in [target doc]"
```

Example: "This fail-closed policy should be canonical in GOVERNANCE_OVERVIEW.md"

---

### Step 2: Tag Speculative Content

**Apply status tag when adding content**:
- If code exists and tests pass → `[IMPLEMENTED]`
- If branch exists or task queued → `[IN_PROGRESS]`
- If only spec/EPIC exists → `[DESIGN_ONLY]`
- If only discussed in chat → `[SPECULATIVE]`
- If code exists but untested → `[NEEDS_VALIDATION]`

**Tag evolution**: Update tags as work progresses:
```
[SPECULATIVE] → [DESIGN_ONLY] → [IN_PROGRESS] → [IMPLEMENTED]
```

**Transparency principle**: Always tag speculative content clearly. Never represent speculative ideas as implemented features.

---

### Step 3: Placement Decision Tree

Use this decision tree to determine target document:

```
┌─────────────────────────────────────────────────────────────┐
│ Is it a guarantee/constraint/architectural principle?       │
│ → docs/GOVERNANCE_OVERVIEW.md                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Is it about attestation/replay/record mechanics?            │
│ → docs/dev/ATTESTATION_SPEC.md                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Is it an application/use case/downstream consumer?          │
│ → docs/dev/APPLICATIONS_INDEX.md                            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Is it operational procedure/workflow?                       │
│ → docs/dev/RUNBOOK.md or docs/dev/OPS_CANONICAL.md         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Is it a feature specification?                              │
│ → docs/EPIC_[NAME].md or dedicated spec doc                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Is it implementation detail (function signature, etc.)?     │
│ → Code comments, inline docs, or defer until needed         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Unsure where it belongs?                                    │
│ → Add to "Open Questions / Needs Placement" section         │
│   in the closest relevant doc                               │
│ → Create task to resolve placement later                    │
└─────────────────────────────────────────────────────────────┘
```

**Document-specific guidance**:

- **GOVERNANCE_OVERVIEW.md**: High-level, conceptual, public-facing. Avoid implementation details.
- **ATTESTATION_SPEC.md**: Technical, object schemas, process flows, replay mechanics. Audience: implementers.
- **APPLICATIONS_INDEX.md**: Use cases, integrations, status-tagged feature list. Audience: application developers.
- **RUNBOOK.md**: Step-by-step operational procedures. Audience: operators (Cecil, Codex, human).
- **OPS_CANONICAL.md**: Script registry, allowlists, invariants. Audience: governance auditors.

---

### Step 4: Ingestion Task Pattern

**Small ingestion** (< 5 lines, clarifying content):
- **Action**: Proceed immediately without task creation
- **Commit message**: "Add [concept] clarification to [doc]"
- **Example**: Adding a sentence explaining a term in GOVERNANCE_OVERVIEW.md

**Large ingestion** (new section, > 20 lines, or new top-level doc):
- **Action**: Create formal task or ask for review
- **Task template**:
  ```markdown
  TASK_ID: AUTO
  Title: Ingest [topic] from chat [date] into canonical docs
  Executor: Cecil
  Status: Ready
  Dependencies: None

  ## Goal
  Canonicalize [concept] discussed in chat [date/session] into [target doc].

  ## Source Context
  Chat session: [date or identifier]
  Key concepts: [bullet list]

  ## Target
  Document: [path to doc]
  Section: [section name or "new section"]
  Status tag: [tag to apply]

  ## Files allowed to touch
  [target doc path]
  docs/dev/evidence/[TASK_ID]/**

  ## Evidence
  - Git diff showing doc update
  - Confirmation that content is canonical (not speculative) or properly tagged
  ```

**When to create task vs proceed**:
- **Proceed directly**: Clarifications, fixing typos, adding index links, tagging status
- **Create task**: New top-level docs, architectural changes, large feature documentation

---

### Step 5: Review Cycle

**Cecil proceeds directly for**:
- Adding clarifying content to existing sections
- Creating new sections in established docs
- Adding index/navigation links
- Tagging speculative content with appropriate status markers
- Fixing typos, formatting, broken links
- Adding "Open Questions / Needs Placement" sections

**Format**: State assumption and proceed
```markdown
Proceeding with [action].
Safe default: [rationale]
If this assumption is incorrect, please correct and I'll adjust.
```

**Create task for Greg review when**:
- Creating new top-level documentation file
- Changing architectural principles or guarantees
- Marking something as [IMPLEMENTED] when tests are ambiguous
- Resolving contradictions between existing docs
- Large refactors (> 50 line changes to established docs)

**Format**: Present plan, wait for approval
```markdown
Proposing [action].
Rationale: [why this is needed]
Impact: [what changes, what stays same]
Alternative: [other options considered]

Awaiting approval before proceeding.
```

---

## Examples

### Example 1: Simple Clarification (Proceed Directly)

**Context**: Chat discussed fail-closed behavior but GOVERNANCE_OVERVIEW.md doesn't explain it clearly.

**Action**:
```bash
# Read current doc
Read docs/GOVERNANCE_OVERVIEW.md

# Add clarifying paragraph to "Fail-Closed Behavior" section
Edit docs/GOVERNANCE_OVERVIEW.md

# Commit with clear message
git add docs/GOVERNANCE_OVERVIEW.md
git commit -m "Clarify fail-closed error handling in governance overview"
git push origin main
```

**No task needed**: Small additive change, non-controversial, auditable via git.

---

### Example 2: Large Ingestion (Create Task)

**Context**: Chat discussed "Case Strength" application concept in detail (citation scoring, attestation chains, confidence metrics). Needs formal canonicalization.

**Action**:
```bash
# Create seed entry for ingestion task
Edit docs/dev/task-seeds/SEED.md

# Add seed entry:
=== SEED ===
STATUS: READY
TASK_ID: AUTO
EXECUTOR: Cecil
TITLE: Ingest Case Strength concept into APPLICATIONS_INDEX.md
DEPENDENCIES: None
GOAL: Canonicalize Case Strength citation layer concept from chat session 2026-02-24 into APPLICATIONS_INDEX.md with [SPECULATIVE] tag.
NON_GOALS: Implementation, formal specification
ALLOWED_FILES:
docs/dev/APPLICATIONS_INDEX.md
docs/dev/evidence/TASK_XXX/**
===

# Generate task
python3 scripts/task_scaffold.py

# Claim and execute task
system/scripts/queue-claim.sh TASK_XXX Cecil
# [work on task]
# [create evidence bundle]
# [merge via Cecil]
```

---

### Example 3: Uncertain Placement (Use Open Questions)

**Context**: Chat discussed "policy evolution versioning" but it's unclear if this belongs in ATTESTATION_SPEC.md, GOVERNANCE_OVERVIEW.md, or a new EPIC.

**Action**:
```markdown
# Add to ATTESTATION_SPEC.md "Open Questions / Needs Placement" section
Edit docs/dev/ATTESTATION_SPEC.md

## 7. Open Questions / Needs Placement

### Policy Evolution & Versioning
- How to version policy rules over time?
- Can old decisions be re-evaluated under new policies?
- How to handle breaking changes in capability registry?

**Status**: [SPECULATIVE]
**Source**: Chat discussion 2026-02-24
**Needs decision**: Should this be in ATTESTATION_SPEC, GOVERNANCE_OVERVIEW, or new EPIC_POLICY_EVOLUTION.md?

# Commit
git add docs/dev/ATTESTATION_SPEC.md
git commit -m "Add policy versioning open question to attestation spec"
git push origin main
```

**Rationale**: Captures content immediately, defers placement decision, creates audit trail.

---

## Anti-Patterns (Avoid These)

### ❌ Mixing Status Tags
**Wrong**:
```markdown
### Ed25519 Signing [DESIGN_ONLY] [SPECULATIVE]
```
**Right**: Pick one tag based on most advanced state (DESIGN_ONLY if spec exists).

---

### ❌ Unmarked Speculative Content
**Wrong**:
```markdown
### Case Strength
Case Strength scores citations by analyzing attestation chains.
```
**Right**:
```markdown
### Case Strength `[SPECULATIVE]`
**Description**: Scoring system for legal/research citations using attestation chains.
**Status**: Speculative concept discussed in planning sessions, no spec or implementation
```

---

### ❌ Implementation Details in GOVERNANCE_OVERVIEW.md
**Wrong**: Adding function signatures, class hierarchies, or code samples to GOVERNANCE_OVERVIEW.md
**Right**: Keep GOVERNANCE_OVERVIEW.md conceptual. Put implementation details in ATTESTATION_SPEC.md or code comments.

---

### ❌ Creating Tasks for Trivial Changes
**Wrong**: Creating TASK_XXX to fix a typo or add one clarifying sentence
**Right**: Just fix it and commit with clear message.

---

### ❌ Asking Permission for Safe Defaults
**Wrong**: "Should I add this clarification to GOVERNANCE_OVERVIEW.md?"
**Right**: "Adding clarification to GOVERNANCE_OVERVIEW.md (safe default: additive change, auditable via git)."

---

## Integration with Safe Defaults Policy

This ingestion workflow follows the safe defaults policy documented in [RUNBOOK.md](RUNBOOK.md):
- **Proceed without asking** for documentation additions, clarifications, status tagging
- **State assumptions clearly** when making placement decisions
- **Use "Open Questions" sections** instead of asking for immediate placement
- **Create tasks** for large ingestions or architectural changes
- **Ask questions only** when decision has significant implications and no safe default exists

See RUNBOOK.md "Question-Asking Policy" section for full safe defaults policy.

---

## Maintenance

**Periodic review** (quarterly or when docs feel stale):
1. Audit "Open Questions / Needs Placement" sections across all docs
2. Resolve placement for items that now have clarity
3. Update status tags for items that have progressed ([SPECULATIVE] → [DESIGN_ONLY] → [IMPLEMENTED])
4. Remove or archive obsolete speculative content
5. Create tasks for high-priority unplaced content

**Ownership**: Cecil maintains this workflow doc and coordinates periodic reviews.

---

## Related Documentation

- [GOVERNANCE_OVERVIEW.md](../GOVERNANCE_OVERVIEW.md): Conceptual documentation entry point
- [ATTESTATION_SPEC.md](ATTESTATION_SPEC.md): Technical specification for attestation mechanics
- [APPLICATIONS_INDEX.md](APPLICATIONS_INDEX.md): Status-tagged application and use case index
- [RUNBOOK.md](RUNBOOK.md): Operational procedures and safe defaults policy
- [TASK_SEEDS.md](TASK_SEEDS.md): Task generation format for formal ingestion tasks
