# Developer Documentation

This directory contains development workflow documentation and task tracking.

---

## Workflow Overview

### Codex Role
- Creates task branches: `codex/TASK_XXX`
- Implements changes on task branch
- Generates evidence bundle in `docs/dev/evidence/<TASK_ID>/`
- Pushes task branch to origin
- **Does NOT modify** `docs/dev/ASSIGNMENTS.md`

### Cecil Role
- Runs merge queue: `system/scripts/merge-queue.sh`
- Verifies each task branch
- Merges passing branches to main
- Updates `docs/dev/ASSIGNMENTS.md` on main at merge time
- **Sole writer** to ASSIGNMENTS.md

---

## Evidence Bundle System

Each task branch must include a complete evidence bundle.

See [EVIDENCE-CONTRACT.md](./EVIDENCE-CONTRACT.md) for:
- Required bundle structure
- Required files (SUMMARY.md, DIFFSTAT.txt, DIFF.patch, TESTS.txt, RISK.md)
- Generation commands
- Verification process

---

## Key Files

| File | Purpose |
|---|---|
| `ASSIGNMENTS.md` | Task ownership tracking (Cecil writes on main only) |
| `EVIDENCE-CONTRACT.md` | Evidence bundle specification |
| `WORK_QUEUE.md` | Task planning queue (if present) |
| `OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md` | Canonical ops process for ChatGPT/Codex/Cecil/Greg collaboration |

---

## Scripts

| Script | Purpose | User |
|---|---|---|
| `system/scripts/verify-branch.sh` | Verify task branch meets requirements | Codex or Cecil |
| `system/scripts/merge-queue.sh` | Verify and merge passing branches | Cecil only |
| `system/scripts/codex-batch.sh` | Generate batch instructions (read-only, no claiming) | Codex |
| `system/scripts/cecil-runloop.sh` | Run Cecil merge + task loop | Cecil only |
| `system/scripts/task-watermark.sh` | Check READY task pool level | Cecil (automatic) |
| `system/scripts/queue-list-next.sh` | List next READY tasks from WORK_QUEUE | Both |
| `system/scripts/queue-claim.sh` | Claim task for actor | Both |
| `system/scripts/queue-complete.sh` | Mark task complete | Both |
| `scripts/task_scaffold.py` | Generate task files from seed file | Cecil (prompted) |
| `scripts/dev/precommit-guard-assignments.sh` | Optional pre-commit hook (not auto-installed) | Codex |

---

## Run Loops

Unattended sequential work is managed through capped run loops driven by repository state.

### Codex Batch Mode

```bash
# Generate next batch of tasks (up to cap)
cd /Volumes/SSD/archive/gov/governance-layer
system/scripts/codex-batch.sh
```

This will:
- Read `codex_max_tasks_per_run` from `system/ops/limits.json`
- List next READY tasks from WORK_QUEUE.md "Next" section
- Generate batch instructions in `ops/CODEX_BATCH.txt` (deterministic, tracked in git)
- Print task files, branch names, and evidence requirements
- **Advisory only**: Does NOT claim tasks or modify WORK_QUEUE.md
- Task claiming/completion must be done separately via queue-claim.sh / queue-complete.sh

### Cecil Run Loop

```bash
# Run Cecil's merge + task loop (capped)
cd /Volumes/SSD/archive/gov/governance-layer
system/scripts/cecil-runloop.sh
```

This will:
1. **Merge Phase**: Run merge-queue.sh with `cecil_max_merges_per_run` limit
2. **Watermark Phase**: Check READY task pool level
   - If pool is low (< `READY_MIN`, default 8) and seed file exists
   - Prompt user to approve running task scaffolder
   - If approved, run dry-run first, then optionally write to new branch
   - **Does NOT auto-merge** scaffold branches (requires manual approval)
   - **Does NOT invent tasks** (only generates from seed file)
3. **Task Phase**: Claim next `cecil_max_tasks_per_run` READY tasks
4. Generate execution plan in `ops/CECIL_PLAN.txt`

#### Watermark Configuration

Set `READY_MIN` environment variable to control watermark threshold:
```bash
READY_MIN=10 system/scripts/cecil-runloop.sh
```

Default: 8 tasks

When triggered:
- User is prompted for approval (non-interactive scaffolder run not allowed)
- Dry-run shows planned outputs before write
- Write creates branch `feat/seed-scaffold-YYYYMMDD` with generated tasks
- Branch is pushed but NOT merged (Greg must approve merge)
- No modification to existing task files or WORK_QUEUE.md (Phase A policy)

### Configuration

Caps are defined in `system/ops/limits.json`:
```json
{
  "codex_max_tasks_per_run": 4,
  "cecil_max_tasks_per_run": 3,
  "cecil_max_merges_per_run": 5
}
```

### State Files

- `WORK_QUEUE.md`: Canonical task queue (Next section is prioritized)
- `ops/CODEX_BATCH.txt`: Generated batch instructions for Codex (tracked in git, deterministic)
- `ops/CECIL_PLAN.txt`: Generated execution plan for Cecil
- `ASSIGNMENTS.md`: Updated by Cecil at merge time only

---

## Governance Rules

1. **Single Writer**: Only Cecil modifies ASSIGNMENTS.md, only on main
2. **Evidence Required**: All task branches must include complete evidence bundle
3. **CI Enforcement**: GitHub Actions fails codex branches that touch ASSIGNMENTS.md
4. **Union Merges**: ASSIGNMENTS.md uses union merge strategy (automatic via .gitattributes)
5. **Verification**: Only verified branches enter merge queue
6. **Fail Closed**: Verification failures block merge

---

## Quick Start for Codex

```bash
# 1. Create task branch
git checkout -b codex/TASK_XXX

# 2. Implement changes
# ... make your changes ...

# 3. Generate evidence bundle
TASK_ID="TASK_XXX"
mkdir -p docs/dev/evidence/$TASK_ID

# Generate artifacts (see EVIDENCE-CONTRACT.md for details)
git diff --stat origin/main...HEAD > docs/dev/evidence/$TASK_ID/DIFFSTAT.txt
git diff origin/main...HEAD > docs/dev/evidence/$TASK_ID/DIFF.patch

# Create SUMMARY.md, TESTS.txt, RISK.md manually

# 4. Verify before pushing
system/scripts/verify-branch.sh codex/TASK_XXX

# 5. Push
git push origin codex/TASK_XXX
```

---

## Quick Start for Cecil

```bash
# Run merge queue to process all verified branches
cd /Volumes/SSD/archive/gov/governance-layer
system/scripts/merge-queue.sh
```

The queue will:
- Fetch latest changes
- Enumerate codex/TASK_* branches
- Verify each branch
- Merge passing branches
- Update ASSIGNMENTS.md at merge time
- Push after each successful merge

