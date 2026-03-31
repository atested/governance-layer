# MERGE_GATE.md
Gate checklist. Gate owner runs this before approving any PR on the `docs/dev` workflow.
All items must be checked. Fail-closed: if any item is uncertain, do not merge.

---

## Global Execution Rules (applies to all tasks)

These rules are always in force for every executor on every task. They are not
overridable by individual task files.

1. **Execute only what the task specifies.** No extra deliverables.
2. **If instructions are ambiguous or require judgment, FAIL CLOSED:** stop and
   report as a blocker. Do not guess.
3. **Do not modify referenced artifacts unless explicitly allowed** in the task's
   Allowed Files.
4. **Forbidden files are absolute.** If touching them seems necessary, stop and
   report.

---

## Pre-merge checklist

### 1. Task file
- [ ] A task file exists at `docs/dev/tasks/*/TASK_NNN__*.md`
- [ ] Task file matches the actual work performed (scope, files, procedure)
- [ ] TASK_ID in file header matches branch name and commit messages

### 2. Assignment handshake
- [ ] Claim commit (`chore(assign): claim TASK_NNN`) is the **first** commit on the branch
- [ ] Complete commit (`chore(assign): complete TASK_NNN`) is the **last** commit on the branch
- [ ] ASSIGNMENTS.md Active entry was present during work
- [ ] ASSIGNMENTS.md History entry is present with Status: Completed

### 3. File scope
- [ ] Only files in the allowed paths for this task were modified
- [ ] No files in forbidden paths were touched
- [ ] `git diff --stat main...HEAD` shows no unexpected files

### 4. Acceptance criteria
- [ ] Every acceptance criterion in the task file is satisfied
- [ ] Observable evidence is provided for each criterion (not just claimed)

### 5. Evidence packet
- [ ] `git status` output provided (working tree clean on branch)
- [ ] `git diff --stat main...HEAD` output provided
- [ ] File list with line counts provided
- [ ] First and last commit messages (`git log --oneline main..HEAD`) provided
- [ ] ASSIGNMENTS.md Active / History sections pasted
- [ ] Command outputs proving each acceptance criterion provided
- [ ] Deviations section present (even if "none")

### 6. Collision check
- [ ] No other active task in ASSIGNMENTS.md modifies the same files
- [ ] WORK_QUEUE.md was updated to reflect new task status

### 7. Fail-closed rule
If any checklist item above is incomplete or uncertain:
- **Do not merge.**
- Return the PR with a comment listing the specific failures.
- Executor must address and re-submit evidence.

### 8. ASSIGNMENTS.md union check (required whenever merge touches ASSIGNMENTS.md)

`ort` may silently drop History rows without raising a conflict marker.
Even if the merge completes cleanly, the executor must verify union correctness before push.

**Resolution rule:** no drops, dedupe by TASK_ID only. Both sides' History rows must survive.

**Post-merge verification sequence (run on the merge commit, before push):**
```
git show --name-only --oneline -1      # confirm ASSIGNMENTS.md is in the merge commit
grep "| TASK_" docs/dev/ASSIGNMENTS.md # list all History rows
```

Checklist:
- [ ] Every TASK_ID contributed by the incoming branch is present in post-merge History
- [ ] Every TASK_ID that was in main's History before the merge is still present
- [ ] `grep` output is included in the evidence packet
- [ ] If any row was silently dropped: restore it in a follow-on commit before push

---

## Gate owner actions on approval

1. Check all boxes above in this document (or in the PR review).
2. Merge branch to `main` (no squash unless evidence would be lost).
3. Move task file from `tasks/ready/` or `tasks/blocked/` to `tasks/done/`.
4. Update WORK_QUEUE.md: move row from Now/Next/Backlog to Done with completion date.
5. Confirm ASSIGNMENTS.md History entry is present and accurate.

---

## Gate owner actions on rejection

1. Comment on PR with specific checklist items that failed.
2. Do NOT merge.
3. Executor corrects and pushes new commits to same branch.
4. Gate owner re-reviews from Step 1.
