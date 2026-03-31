# RUNBOOK

## What this is
Single operational entrypoint for running the system: Codex, Cecil, Qt.

## Session Start Protocol (Cecil REQUIRED)

**MANDATORY**: At the beginning of every session involving tool execution or operational tasks, Cecil MUST:

1. ☑ Read `docs/dev/AGENT_CONTRACT.md` - Confirmation policy and safe defaults
2. ☑ Read this file (`docs/dev/RUNBOOK.md`) - Operational procedures
3. ☑ Read `docs/dev/OPS_CANONICAL.md` (if merge operations expected)
4. ☑ Acknowledge compliance in first operational message

**Compliance acknowledgment format**:
```
Session initialized. AGENT_CONTRACT.md confirmation policy active:
- Read-only operations: proceed automatically
- State changes: proceed with stated assumptions per safe defaults
- High-risk operations: ask first
```

**Why this matters**: AGENT_CONTRACT.md defines the binding rule for when to ask vs proceed. Without reading it at session start, Cecil may ask unnecessary questions or miss required confirmations.

**Enforcement**: Violations (asking about read-only operations, proceeding without stating assumptions) should be corrected immediately by re-reading AGENT_CONTRACT.md.

See [AGENT_CONTRACT.md](AGENT_CONTRACT.md) for detailed command-level confirmation policy.

---

## Sources of truth
- `docs/dev/OPS_CANONICAL.md` - Canonical ops record, lanes, invariants, script registry
- `docs/dev/PLANNER_SNAPSHOT.md` - Current system state and planning context
- `docs/dev/inventory/INVENTORY_LATEST.md` - Deterministic inventory snapshot
- `docs/dev/TASK_SEEDS.md` - Task seed definitions and generation rules
- `docs/dev/WORK_QUEUE.md` - Task queue and status tracking

## System lanes

### Codex lane
**Executor**: Codex CLI only
**Branches**: `codex/*` topic branches only
**Constraints**:
- Touch only Allowed Files specified by task spec
- Must produce evidence bundles when required
- Must push branch to origin
- Never merges to main
- Never modifies ASSIGNMENTS.md or WORK_QUEUE

**Tools**:
- `system/scripts/codex-batch.sh` - Generate read-only task list
- `system/scripts/codex-unattended.sh` - Unattended task runner with preflight, Allowed Files enforcement, evidence validation

**Typical flow**:
```bash
bash system/scripts/codex-batch.sh           # Generate ops/CODEX_BATCH.txt
bash system/scripts/codex-unattended.sh run-one TASK_XXX
```

### Cecil lane
**Executor**: Cecil (governance-authorized operator)
**Authority**:
- Sole merger to main
- Sole writer of docs/dev/ASSIGNMENTS.md on main at merge time
- Enforces invariants and resolves conflicts per governance rules

**Tools**:
- `system/scripts/cecil-runloop.sh` - Cecil execution loop (may claim tasks)
- `system/scripts/queue-claim.sh` - Task claiming (Cecil only)
- `scripts/verify-ops-canonical.py` - Canonical ops verification

**Typical merge flow**:
```bash
git fetch origin --prune
git switch main
git reset --hard origin/main
bash system/scripts/inventory-snapshot.sh
python3 scripts/verify-ops-canonical.py
git merge --no-ff origin/codex/TASK_XXX -m "Merge codex/TASK_XXX"
# Update docs/dev/ASSIGNMENTS.md (Cecil sole writer on main)
git push origin main
```

### Qt lane
**Executor**: Qt (Queen of the Tests) - QA model via Ollama
**Model**: `qt:latest` (qwen2.5:7b-instruct base)
**Constraints**:
- QA tester and adversarial auditor only
- May write only to `qa/test-plans/` and `qa/evidence/`
- No patch suggestions, no code edits, fail closed on invalid requests
- Evidence packets must include sha256

**Current status**: Bootstrapped and operational
**Evidence**: `qa/evidence/bootstrap/QA_BOOTSTRAP__sister3-qa__qwen2.5-7b-instruct.md`

**Operator steps**:
```bash
bash system/scripts/qt-runner.sh docs/dev/qt-jobs/QT_JOB_001__merge_readiness.md
```
- Qt job definitions live in `docs/dev/qt-jobs/`
- Qt runner outputs live in `docs/dev/evidence/QT/<JOB_ID>/`:
  - `TESTS.txt` (raw command outputs)
  - `QT_REPORT.md` (Qt evaluation summary)

**Typical QA flow**:
```bash
ollama run qt "JOB_ID: QA_XXXX
CAPABILITY: <capability_name>
PHASE: 1
..."
```

## Seeds

### Location(s)
- `docs/dev/TASK_SEEDS.md` - Main seed registry and generation rules
- `docs/dev/task-seeds/SEED.md` - Seed specification format
- `docs/dev/task-seeds/SEED_EXAMPLE.md` - Example seed

### What qualifies as a seed
A seed is a structured specification for generating one or more tasks. Seeds define:
- Goal/objective
- Acceptance criteria
- Allowed Files patterns
- Evidence requirements
- Dependencies
- Phase/readiness constraints

### How seeds are consumed
Seeds are processed by `scripts/task_scaffold.py` to generate executable task specifications under `docs/dev/tasks/ready/`.

**Generation command**:
```bash
python3 scripts/task_scaffold.py --seed docs/dev/task-seeds/<seed_file>.md
```

## Task generation

### Current mechanism
**Primary tool**: `scripts/task_scaffold.py`

**Inputs**:
- Seed files from `docs/dev/task-seeds/`
- Task template from `docs/dev/TASK_TEMPLATE.md`
- Capability metadata (optional)

**Outputs**:
- Task specification files: `docs/dev/tasks/ready/TASK_XXX__<title>.md`
- Updates to `docs/dev/WORK_QUEUE.md` (via separate process)

**Constraints**:
- **Allowed Files**: Must be explicitly specified in task spec under "Files allowed to touch" or "Allowed Files" section
- **Evidence paths**: Must be under `docs/dev/evidence/TASK_XXX/` with `TESTS.txt` required
- **Determinism**: Task outputs must be reproducible with same inputs
- **Naming**: `TASK_XXX` format where XXX is zero-padded 3-digit number

### Failure modes
1. **Parser/spec format mismatch**: Allowed Files parser expects specific format (bullets under header)
2. **Evidence path mismatch**: Evidence must match `docs/dev/evidence/TASK_XXX/` pattern
3. **Missing evidence**: `TESTS.txt` must exist in evidence directory
4. **Allowed Files violation**: Changes outside permitted paths trigger verification failure

## Normal run loop

### 1) Generate batch list
```bash
cd /Volumes/SSD/archive/gov/governance-layer
bash system/scripts/codex-batch.sh
# Outputs: ops/CODEX_BATCH.txt (deterministic, read-only)
```
Selection rule (enforced by `codex-batch.sh`): only include task specs that contain
`Executor: Codex`, do not declare `Branch: n/a`, and include an allowlist header
(`## Allowed Files` or `## Files allowed to touch`, case-insensitive).

### 2) Codex executes tasks
**Unattended mode** (recommended):
```bash
bash system/scripts/codex-unattended.sh run-one TASK_XXX
```

**Manual mode**:
```bash
# In Codex workspace: ~/codex-workspaces/governance-layer
codex run --task TASK_XXX
```

### 3) Cecil merges
For each completed Codex branch:
```bash
git fetch origin --prune
git switch main
git reset --hard origin/main
bash system/scripts/inventory-snapshot.sh
python3 scripts/verify-ops-canonical.py
git merge --no-ff origin/codex/TASK_XXX -m "Merge codex/TASK_XXX"
bash system/scripts/inventory-snapshot.sh
python3 scripts/verify-ops-canonical.py
# Update docs/dev/ASSIGNMENTS.md
git add docs/dev/ASSIGNMENTS.md docs/dev/inventory/INVENTORY_LATEST.md
git commit -m "Update ASSIGNMENTS.md and inventory for TASK_XXX merge"
git push origin main
```

### 4) Verification gates
All gates must pass before push:
- `python3 scripts/verify-ops-canonical.py` returns OK
- `bash system/scripts/inventory-snapshot.sh` generates clean inventory
- Evidence packets exist with required TESTS.txt
- Allowed Files compliance verified

### Release gate (Phase 3 signing readiness)
Before declaring Phase 3 signing stable or promoting signing-related branches, run the release gate script:
```
bash system/scripts/release-gate.sh
```
It compiles the core signing tooling, runs `tests/test_signing_key_loading.sh`, `tests/test_signing_emit.sh`, and `tests/test_verify_signatures.sh`, and fails fast if any step regresses. Each command echoes with `$ `, emits a `[exit=N]` marker, and the canonical transcript lives in `docs/dev/evidence/OPS_RELEASE_GATE/TESTS.txt` so Cecil can verify the gate run.
Run the gate whenever you touch signing-related logic or before switching the signing capability to `[IMPLEMENTED]` on the merge board.

**What it proves**:
- Signing emit present and deterministic (signature field populated, Ed25519 deterministic behavior)
- Verifier passes (record hash verification, signature verification, chain validation)
- Key loading paths covered (no key → unsigned mode, key configured → signing attempted)
- Core tooling syntactically valid (policy-eval.py, verify-record.py, verify-chain.py, replay-record.py compile)

**Evidence path**: `docs/dev/evidence/OPS_RELEASE_GATE/TESTS.txt`

**If it fails**:
- Check the transcript for which test failed (`[exit=N]` markers show failure points)
- Rerun `bash system/scripts/release-gate.sh` after fixes
- Attach transcript to branch evidence if reporting regression

## Failure playbook

### Dirty tree
**Symptom**: `git status --porcelain` shows uncommitted changes
**Resolution**:
```bash
git stash push -u -m "cleanup before merge"
git reset --hard origin/main
```

### Stale local task branches
**Symptom**: Local branch exists but diverged from origin
**Resolution**:
```bash
git branch -D codex/TASK_XXX
git fetch origin --prune
git checkout -b codex/TASK_XXX origin/codex/TASK_XXX
```

### Evidence path mismatch
**Symptom**: Evidence exists but not at expected path
**Resolution**: Update task spec to include correct evidence path in Allowed Files:
```
- docs/dev/evidence/TASK_XXX/**
```

### Network/DNS
**Symptom**: Preflight checks fail on DNS or SSH
**Resolution**: Retry with backoff (codex-unattended.sh has built-in retry logic for DNS/SSH checks)

### Parser/spec format mismatch
**Symptom**: Allowed Files parser fails to extract patterns
**Resolution**: Ensure task spec uses canonical format:
```markdown
## Files allowed to touch
- path/to/file1.md
- path/to/pattern/**
```
Or:
```markdown
## Allowed Files
- path/to/file1.md
```

## Diagnostics (No UI Approvals)

## MCP smoke dependency semantics

`tests/run-mcp-smoke.sh` supports deterministic dependency semantics:
- `SKIP`: required MCP dependency is unavailable in the selected interpreter.
- `FAIL`: dependency exists, smoke ran, but contract checks failed.

Enable full mode with canonical repo-local interpreter:
```bash
python3 -m venv mcp/.venv
mcp/.venv/bin/python3 -m pip install -r mcp/requirements.txt
GOV_RUNTIME_DIR=${GOV_RUNTIME_DIR:-gov_runtime} bash tests/run-mcp-smoke.sh
```

When recording evidence, include `[exit=...]` markers and two-run SHA256 digest equality.

### Purpose
Helper scripts for common read-only diagnostic patterns that avoid triggering UI approval prompts. These scripts batch multiple read operations into single invocations.

### Available Scripts

#### throughput-report.sh
Parse and report on throughput loop execution logs.

**Location**: `system/scripts/throughput-report.sh`

**Usage**:
```bash
# Show all throughput logs
bash system/scripts/throughput-report.sh

# Show last 3 logs
bash system/scripts/throughput-report.sh --last 3

# Filter to specific task
bash system/scripts/throughput-report.sh --task TASK_104

# Combined filters
bash system/scripts/throughput-report.sh --last 1 --task TASK_092
```

**Output sections**:
- Published Tasks: `TASK_### CODE|EVIDENCE_ONLY origin/codex/TASK_###__hash`
- Errors and Stops: Lines matching `STOP:|fatal:|TIMEOUT|ERROR:`
- Summary: `CODE: X, EVIDENCE_ONLY: Y`
- Execution Time: `real/user/sys` timing if present
- Overall Summary: Totals across all selected logs

**Log location**: `/tmp/throughput*.log`

#### classify-branches.sh
Classify unmerged codex branches as CODE or EVIDENCE_ONLY.

**Location**: `system/scripts/classify-branches.sh`

**Usage**:
```bash
bash system/scripts/classify-branches.sh
```

**Output**: Lines of format `origin/codex/TASK_XXX__hash CODE|EVIDENCE_ONLY`

#### list-code-branches.sh
List unmerged CODE branches (branches with changes outside `docs/dev/evidence/`).

**Location**: `system/scripts/list-code-branches.sh`

**Usage**:
```bash
bash system/scripts/list-code-branches.sh
```

**Output**: One branch per line, format `origin/codex/TASK_XXX__hash`

### Tool Selection Guidance

Per [AGENT_CONTRACT.md](AGENT_CONTRACT.md), prefer these approaches for diagnostics:

**Preferred** (no UI approval prompts):
- Read/Grep/Glob tools for file operations
- Helper scripts for repeated patterns
- Single git commands (`git status`, `git log`, `git branch`)

**Avoid** (triggers UI approvals):
- Bash loops over git output
- Complex piped commands
- Multiple chained grep/awk/sed operations

---

## Question-Asking Policy (Safe Defaults for Cecil)

### Operating Principle
Proceed with safe defaults and state assumptions clearly. Ask questions only when decision has significant implications and no safe default exists.

### Category 1: File Operations (Proceed Without Asking)
- ✓ Prefer Edit over Write for existing files
- ✓ Read before editing/writing
- ✓ Create new files when task explicitly requires them
- ✓ Read any file to gather context
- ✓ Use git history to understand changes
- **Format**: "Reading [file] to understand [context]" (no question)

### Category 2: Documentation (Proceed Without Asking)
- ✓ Add clarifying content, fix typos, formatting
- ✓ Add index/navigation sections
- ✓ Add "Open Questions / Needs Placement" sections for unresolved items
- ✓ Add status tags ([IMPLEMENTED], [SPECULATIVE], etc.)
- ✓ Create canonical docs when plan is approved
- **Format**: "Adding [content] to [doc] (safe default: auditable via git)"

### Category 3: Code Operations (Proceed Without Asking)
- ✓ Read any code to understand implementation
- ✓ Run tests to verify behavior
- ✓ Check git status, branch state, history
- ✓ Run non-destructive analysis commands
- **Format**: "Running [command] to verify [behavior]"

### Category 4: Task Workflow (Proceed Without Asking)
- ✓ Use TodoWrite for multi-step tasks
- ✓ Mark todos as in_progress/completed as work proceeds
- ✓ Update ASSIGNMENTS.md following UNION rule
- ✓ Run inventory-snapshot.sh and verify-ops-canonical.py
- ✓ Commit inventory updates after verification
- **Format**: "Updating [workflow artifact] per established protocol"

### Category 5: Merge Operations (Proceed Without Asking)
- ✓ Merge CODE branches using established protocol (no-ff, verify, ASSIGNMENTS update, push)
- ✓ Hold EVIDENCE_ONLY branches by default
- ✓ Resolve inventory conflicts with --theirs + regenerate
- ✓ Skip conflicting variant branches (document in HELD_EVIDENCE_ONLY.md)
- **Format**: "Merging [branch] per morning merge protocol"

### Category 6: Default to Fail-Closed (Proceed Without Asking)
- ✓ If uncertain about safety, choose safest reversible option
- ✓ If operation is git-reversible, proceed with clear commit message
- ✓ If multiple safe approaches exist, pick one and state rationale
- **Format**: "Proceeding with [approach] (fail-closed: [rationale])"

### When to Ask Questions (Only These 5 Situations)

**1. Architectural decisions with competing tradeoffs**
- Example: "Should we store evidence in repo (auditable) or separate store (smaller repo)?"
- Present recommendation + rationale, but acknowledge alternatives have meaningful tradeoffs

**2. Destructive operations**
- Force-pushing to main
- Deleting branches with unmerged commits
- Modifying published/signed artifacts

**3. Policy/governance changes**
- Changes to OPS_CANONICAL.md script allowlists
- Changes to capability registry enforcement rules
- Changes to merge gate rules

**4. Genuinely ambiguous scope**
- Task description has multiple valid interpretations AND choice significantly affects downstream work
- Not "should I do this?" but "which of these 2+ valid interpretations matches your intent?"

**5. Priority/sequencing with significant implications**
- "Should I merge these 10 branches now (risk rate limit) or batch them tomorrow?"
- Only when timing affects correctness or system state

### Format for Proceeding with Assumptions
```
Proceeding with [action].
Safe default: [rationale]
If this assumption is incorrect, please correct and I'll adjust.
```

**Example**: "Proceeding with creating docs/GOVERNANCE_OVERVIEW.md per approved plan. Safe default: new file, auditable via git, non-destructive."

### Integration with Ingestion Workflow
This policy aligns with the ingestion workflow documented in [INGESTION_WORKFLOW.md](INGESTION_WORKFLOW.md). See that document for detailed guidance on canonicalizing chat-derived content.

---

## Qt workstream

### Current status/limitation
- ✓ Qt model bootstrapped and operational (`qt:latest` via Ollama)
- ✓ Hard rules enforced (QA-only, no code edits, evidence packets with sha256)
- ⚠️ Runtime responsiveness test shows model treats all input as QA job specification
- ✓ Evidence: `qa/evidence/bootstrap/QT_QUICKCHECK.md` (Classification: FAIL - does not echo simple input)

### Target behavior
- QA validation runs via structured job specifications
- Phase-gated smoke contract validation
- Evidence packet generation with deterministic reproduction steps
- Integration with merge gate for capability validation

### Plan
1. Define QA job batch format compatible with qt constraints
2. Create QA job runner that feeds properly formatted jobs to qt
3. Integrate QA evidence validation into merge gate
4. Expand Phase 1 coverage to all deterministic capabilities

## Current findings (auto-scan)

### SEED file candidates
- `./docs/dev/TASK_SEEDS.md` - Main seed registry
- `./docs/dev/task-seeds/SEED_EXAMPLE.md` - Example seed format
- `./docs/dev/task-seeds/SEED.md` - Seed specification

### Task generation tools
- `scripts/task_scaffold.py` - Primary task generation script

### Scripts referencing tasks/ready
- `system/scripts/cecil-runloop.sh` - Cecil execution loop
- `system/scripts/codex-batch.sh` - Batch task lister
- `system/scripts/codex-unattended.sh` - Unattended task runner
- `system/scripts/inventory-snapshot.sh` - Inventory generator (lists tasks)
- `system/scripts/task-watermark.sh` - Task watermarking utility

### Operational docs inventory
- ASSIGNMENTS.md - Task ownership tracking (Cecil sole writer on main)
- EPIC_PROMOTION.md - Cross-root promotion design
- EPIC_SIGNING.md - Phase 3 signing spec
- EVIDENCE-CONTRACT.md - Evidence packet requirements
- FS_DELETE_SCHEMA.md - FS_DELETE intent schema
- INVARIANTS_MAP.md - System invariants INV-001..008
- MERGE_GATE.md - Merge gate rules
- OPS_CANONICAL.md - Canonical ops record
- PLANNER_SNAPSHOT.md - Current state snapshot
- README.md - docs/dev overview
- REASON_CODES.md - Reason code index
- TASK_SEEDS.md - Task seed definitions
- TASK_TEMPLATE.md - Task specification template
- WORK_QUEUE.md - Task queue and status

## Throughput operator notes

### queue-drift-scan usage
- Run informationally before throughput batches:
  - `python3 system/scripts/queue-drift-scan.py`
- Recommended operator sequence before a throughput push:
  - `python3 system/scripts/queue-drift-scan.py` then `GOV_PROFILE=dev bash system/scripts/release-gate.sh`
- Use blocking mode only when you want drift to fail the step:
  - `python3 system/scripts/queue-drift-scan.py --exit-on-drift`
- Interpret output:
  - `READY tasks with published branches pending merge` means throughput should avoid rerunning those tasks until merged/reconciled.
  - `non-parseable allowlists` means fix/normalize specs before unattended execution.
  - `Done lacking provenance note` means governance docs need reconciliation, not code work.

### release-gate usage (proof-packet section)
- Default mode is non-gating informational proof-packet check:
  - `bash system/scripts/release-gate.sh`
- Profile-driven mode (preferred for operators):
  - `GOV_PROFILE=dev bash system/scripts/release-gate.sh` (informational proof-packet check)
  - `GOV_PROFILE=ci bash system/scripts/release-gate.sh` (strict/gating proof-packet check)
- Strict proof-packet mode (future gating / merge-window checks):
  - `RELEASE_GATE_STRICT_PROOF_PACKET=1 bash system/scripts/release-gate.sh`
- `RELEASE_GATE_STRICT_PROOF_PACKET` overrides `GOV_PROFILE` proof-packet strictness when both are set.
- The proof-packet section prints deterministic `packet_sha` and `summary_sha` values when the sample check succeeds.
- If proof-packet fixtures/tools are unavailable:
  - default mode prints an `INFO:` skip/failure marker and continues
  - strict mode fails closed with a deterministic `FAIL:` marker

### verify-task status semantics
- `verify-task: OK (...)`
  - A verifier hook or deterministic fallback ran and passed.
- `verify-task: INFO (...) hook missing; using fallback ...`
  - Informational line only; final `OK`/`FAIL` is authoritative.
- `verify-task: SKIP (...)`
  - Verification could not run (e.g., missing hard dependency).
  - Returns `rc=3` deterministically and should be handled explicitly by automation/policy.

### MCP smoke dependency / full-mode note
- Deterministic `SKIP` for MCP smoke verification usually means the runner interpreter lacks the `mcp` dependency.
- To enable full mode, install the project MCP requirements into the same interpreter/venv used by the runner (see `mcp/requirements.txt`, or use `system/scripts/bootstrap-run.sh` when available).

## Revision history
- 2026-02-20: Initial runbook created with seeds and task generation mapping
