# TASK_TEMPLATE.md
Copy this file to `docs/dev/tasks/ready/TASK_NNN__short-slug.md` and fill in all fields.
Remove all `<angle-bracket>` placeholders before committing the task file.

---

# TASK_NNN__short-slug.md

TASK_ID: TASK_NNN
Title: <One-line title>
Executor: <Cecil | Greg | Other>
Owner/Gate: <Who approves the evidence packet>
Branch: feat/<slug>-NNN
Status: Ready
Dependencies: <TASK_ID list | none>

## Goal
<1–3 sentences. What specific state change does this task produce?>

## Non-goals
<What this task explicitly does NOT do.>

## Files allowed to touch
- <path pattern, e.g. /docs/dev/**>
- <additional paths if needed>

## Files forbidden to touch
- Everything outside allowed paths above.
- <any explicit exceptions within allowed paths>

## Change budget (optional)
<Max N files, max N lines — omit if not needed.>

---

## Execution Rules (Always On)

These rules apply regardless of task content. Copy them verbatim into every task file.

1. **Execute only what the task specifies.** No extra deliverables.
2. **If instructions are ambiguous or require judgment, FAIL CLOSED:** stop and
   report as a blocker. Do not guess.
3. **Do not modify referenced artifacts unless explicitly allowed** in this task's
   Allowed Files.
4. **Forbidden files are absolute.** If touching them seems necessary, stop and
   report.

---

## Procedure

Step 1 — Assignment handshake (always first)
- Create or update `docs/dev/ASSIGNMENTS.md`:
  - Add Active entry: TASK_ID, Executor, Branch, Status=In Progress, Started=<timestamp>
- Commit: `git add docs/dev/ASSIGNMENTS.md && git commit -m "chore(assign): claim TASK_NNN"`
- This commit must be the first commit on the branch.

Step 2 — <Action>
<Detail. Be specific enough that a different executor could follow without asking questions.>

Step 3 — <Action>
<...>

Step N — Complete assignment handshake (always last)
- Update `docs/dev/ASSIGNMENTS.md`:
  - Move TASK_NNN from Active to History
  - Set Status: Completed, Completed: <timestamp>
  - Add Note if any deviation from procedure
- Commit: `git commit -m "chore(assign): complete TASK_NNN"`

---

## Acceptance criteria

- [ ] <Criterion 1 — observable and binary>
- [ ] <Criterion 2>
- [ ] <Criterion 3>

---

## Evidence packet required

The executor must include ALL of the following in their response:

1. `git status` (must be clean on branch)
2. `git diff --stat main...HEAD`
3. File list of every file created or modified (with line counts)
4. First and last commit messages from `git log --oneline main..HEAD`
5. Paste of ASSIGNMENTS.md Active / History sections
6. Relevant command outputs proving acceptance criteria
7. Deviations: any step skipped or modified, with reason

---

## Return format (strict)

Cecil response must follow this structure:

```
## Summary
- <bullet>
- <bullet>

## Files changed
- <path> — <what changed>

## Evidence
[paste evidence packet here]

## Notes / deviations
<none | description>
```
