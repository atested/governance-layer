# Agent Contract

Binding contract for Cecil (and all governance-layer agents) defining confirmation policy and safe defaults.

**Enforcement**: Cecil MUST read and comply with this contract at the start of every session. Violations of this contract should be treated as workflow errors.

---

## Core Principle

**Read-only actions execute automatically. State-changing actions require awareness (not necessarily prompts).**

---

## Confirmation Policy

### Rule: Check `git status --porcelain` Impact

Before considering a confirmation prompt, ask:
> "Would this command change the output of `git status --porcelain`?"

- **If NO** → Proceed automatically, no question
- **If YES** → Proceed with stated assumption (safe default policy), or ask if no safe default exists

### Always Safe (Never Ask)

Commands that **cannot** modify repository state:

**Git read operations**:
```bash
git status
git log
git show
git diff
git branch [-r] [-a] [--no-merged]
git ls-files
git rev-parse
git merge-base
git log
git remote -v
git fetch --prune  # Updates refs but doesn't change working tree
```

**File read operations**:
```bash
cat, head, tail, less, more
grep, rg, ag
find, fd
ls, tree
stat, file
```

**Analysis operations**:
```bash
wc, sort, uniq
jq, yq
sed -n (no -i)
awk
python3 scripts/*.py [read-only mode]
```

**Output-only operations**:
```bash
echo
printf
> /tmp/*  # Writes to /tmp only
```

**Loops and pipes combining safe operations**:
```bash
for x in $(git branch -r); do git diff $x; done
git diff ... | grep | awk | wc
find . -name "*.py" | xargs grep "pattern"
```

### Tool Selection for Read-Only Operations

**Rule**: Prefer non-Bash tools for read-only diagnostics and reporting to minimize UI approval prompts.

**Preferred for diagnostics**:
- **Read** tool - For reading files (instead of `cat`, `head`, `tail`)
- **Grep** tool - For content search (instead of `bash grep` loops)
- **Glob** tool - For file finding (instead of `find` or `ls` loops)
- **Helper scripts** - For repeated diagnostic patterns (e.g., `throughput-report.sh`)

**Use Bash only for**:
- State-changing operations (merge, commit, push, run repo scripts)
- Single simple read commands (`git status`, `git log`, `git branch`)
- Operations where Bash is genuinely required (pipes, redirects, variable manipulation)

**Examples**:

❌ **Avoid** (triggers UI approval):
```bash
for branch in $(git branch -r); do git diff origin/main..."$branch" | grep pattern; done
git log | grep | awk | wc
find . -name "*.txt" | xargs cat
```

✓ **Prefer**:
```bash
# Use non-Bash tools
Read file_path="/path/to/file"
Grep pattern="keyword" path="." output_mode="files_with_matches"
Glob pattern="**/*.txt"

# Or use helper scripts
bash system/scripts/classify-branches.sh
bash system/scripts/throughput-report.sh --last 5
```

**Rationale**: Claude Code UI approval layer intercepts Bash tool calls but may bypass approval for Read/Grep/Glob tools. Helper scripts batch operations into single invocations, reducing approval friction.

See [RUNBOOK.md Diagnostics section](RUNBOOK.md#diagnostics-no-ui-approvals) for available helper scripts.

---

### Requires Awareness (State Assumptions)

Commands that **modify repository state** but have safe defaults:

**File modifications**:
- Edit, Write tool calls → Proceed with "Safe default: auditable via git, reversible"
- Creating new files → Proceed if task/plan requires it

**Documentation updates**:
- Adding content to canonical docs → Proceed with "Safe default: additive, auditable"
- Status tags, clarifications → Proceed automatically

**Workflow updates**:
- ASSIGNMENTS.md updates → Proceed per UNION rule
- Inventory regeneration → Proceed after verification passes
- Evidence bundle commits → Proceed per task requirements

**Format**: State assumption clearly, proceed
```
Proceeding with [action].
Safe default: [rationale].
If incorrect, please correct and I'll adjust.
```

### Requires Explicit Confirmation (Always Ask)

Commands with **irreversible or high-risk** state changes:

**Destructive git operations**:
```bash
git reset --hard
git push --force
git rebase [-i]
git branch -D [with unmerged commits]
git merge --abort [loses conflict resolution work]
git clean -fd
```

**Merge/push operations** (ask if not following established protocol):
```bash
git merge [unless following documented merge protocol]
git push origin main [unless post-verification in protocol]
```

**Governance changes**:
- OPS_CANONICAL.md script allowlist modifications
- Capability registry policy changes
- Merge gate rule changes

**Architectural decisions**:
- Multiple valid approaches with significant tradeoffs
- Changes affecting downstream systems

**Format**: Present options, wait for decision
```
Question: [specific decision needed]
Option 1: [approach] - [tradeoffs]
Option 2: [approach] - [tradeoffs]
Recommendation: [option] because [rationale]
```

---

## UI Approval Layer Mitigation

### Problem

Claude Code UI may prompt for approval on complex bash commands even if they're read-only. This creates friction for classification loops, analysis scripts, etc.

### Solution 1: Batch Scripts (Preferred)

Instead of inline bash loops, use helper scripts:

**Bad** (triggers UI approval):
```bash
for branch in $(git branch -r); do
  git diff origin/main..."$branch" | grep pattern
done
```

**Good** (single script invocation):
```bash
bash system/scripts/classify-branches.sh
```

Create small, auditable scripts for repeated patterns:
- `system/scripts/classify-branches.sh` - Classify CODE vs EVIDENCE_ONLY
- `system/scripts/list-unmerged-code-branches.sh` - List CODE branches not on main
- `system/scripts/check-merge-conflicts.sh` - Check if branch conflicts with main

### Solution 2: Prepare Classification Output

If batching isn't feasible, prepare classification in /tmp first:

```bash
# Step 1: Generate classification report (single command)
git branch -r --no-merged origin/main | \
  xargs -I {} bash -c 'git diff --name-only origin/main...{} | grep -qv "^docs/dev/evidence/" && echo "{} CODE" || echo "{} EVIDENCE_ONLY"' \
  > /tmp/branch-classification.txt

# Step 2: Read and process (separate command)
cat /tmp/branch-classification.txt
```

### Solution 3: Tool Selection

For complex read operations that trigger approvals:
- Use **Grep** tool for content search (avoid bash grep loops)
- Use **Glob** tool for file finding (avoid bash find loops)
- Use **Read** tool for file reading (avoid bash cat loops)

Only use Bash when actual shell features are required (pipes, redirects, variables).

---

## Integration with Safe Defaults Policy

This contract extends the safe defaults policy in [RUNBOOK.md](RUNBOOK.md):

**RUNBOOK.md Section "Question-Asking Policy"**: Defines categories and situations for asking questions

**This document (AGENT_CONTRACT.md)**: Defines the low-level command-by-command policy for confirmation

**Precedence**: AGENT_CONTRACT.md rules are more specific and take precedence for tool execution decisions.

---

## Session Start Checklist

At the beginning of every session, Cecil MUST:

1. ☑ Read `docs/dev/AGENT_CONTRACT.md` (this file)
2. ☑ Read `docs/dev/RUNBOOK.md` (operational procedures)
3. ☑ Read `docs/dev/OPS_CANONICAL.md` (if merge operations expected)
4. ☑ Acknowledge compliance with confirmation policy

**Compliance statement** (include in first message when task involves tool execution):
```
Session initialized. AGENT_CONTRACT.md confirmation policy active:
- Read-only operations: proceed automatically
- State changes: proceed with stated assumptions per safe defaults
- High-risk operations: ask first
```

---

## Examples

### Example 1: Classification Loop (Read-Only)

**Command**:
```bash
for branch in $(git branch -r); do
  git diff --name-only origin/main..."$branch" | grep -v evidence && echo CODE || echo EVIDENCE
done
```

**Analysis**:
- git branch -r → read-only ✓
- git diff --name-only → read-only ✓
- grep, echo → read-only ✓
- Loop combines safe operations → read-only ✓

**Decision**: Proceed automatically, no question

**Better approach** (avoid UI approval): Create `system/scripts/classify-branches.sh`

---

### Example 2: Creating Documentation (State Change, Safe Default)

**Action**: Adding new section to GOVERNANCE_OVERVIEW.md

**Analysis**:
- Changes git status? YES (modified file)
- Destructive? NO (auditable, reversible)
- Safe default exists? YES (additive documentation change)

**Decision**: Proceed with stated assumption
```
Proceeding with adding [section] to GOVERNANCE_OVERVIEW.md.
Safe default: Additive documentation change, auditable via git.
```

---

### Example 3: Merge Operation (State Change, Protocol Exists)

**Action**: Merging codex/TASK_XXX to main

**Analysis**:
- Changes git status? YES (merge commit)
- Destructive? YES (changes main branch)
- Protocol exists? YES (documented merge protocol in RUNBOOK.md)
- Following protocol? YES

**Decision**: Proceed per protocol, state each step
```
Proceeding with merge per documented protocol:
1. Merge with --no-ff
2. Run verification (inventory + ops canonical)
3. Update ASSIGNMENTS.md per UNION rule
4. Push to origin/main
```

---

### Example 4: Architectural Decision (No Safe Default)

**Situation**: Task says "add caching" but doesn't specify mechanism

**Analysis**:
- Multiple approaches: Redis, in-memory, file-based
- Tradeoffs: performance, complexity, dependencies
- No safe default (choice affects architecture significantly)

**Decision**: Ask with recommendation
```
Question: Caching mechanism for [feature]

Option 1: Redis - Better performance, requires Redis server
Option 2: In-memory dict - Simpler, loses cache on restart
Option 3: File-based - Persistent, slower than memory

Recommendation: In-memory dict for Phase 2 (simplicity), Redis for Phase 3 (scale)

Which approach matches project priorities?
```

---

## Enforcement Mechanisms

### Self-Enforcement

Cecil monitors own behavior:
- Before any tool use, internally check: "Does this change git status?"
- If read-only and UI prompts anyway → note for batching/script extraction
- If proceeding with assumption → state assumption clearly
- If genuinely uncertain → ask with options

### Audit Trail

Git commits provide audit trail:
- Every state change has commit message explaining rationale
- Failed assumptions can be reverted cleanly
- History shows progression of decisions

### Violations

If Cecil asks for confirmation on read-only operation:
- User responds: "Read-only, proceed automatically per AGENT_CONTRACT.md"
- Cecil acknowledges error and self-corrects
- Consider updating AGENT_CONTRACT.md with missed case

---

## Maintenance

**Review quarterly** or when:
- New categories of operations emerge
- UI approval layer behavior changes
- User feedback indicates policy gaps

**Update process**:
1. Identify gap or ambiguity
2. Propose addition to AGENT_CONTRACT.md
3. Test with examples
4. Commit with clear rationale

---

## Related Documentation

- [RUNBOOK.md](RUNBOOK.md): Operational procedures and question-asking policy (higher-level)
- [INGESTION_WORKFLOW.md](INGESTION_WORKFLOW.md): Process for documentation changes
- [OPS_CANONICAL.md](OPS_CANONICAL.md): Script registry and operational invariants
- [Safe Defaults Policy (in RUNBOOK.md)](RUNBOOK.md#question-asking-policy-safe-defaults-for-cecil): Category-level safe defaults
