# EVIDENCE-CONTRACT.md

Defines the standard evidence bundle that Codex must produce for each task branch.

---

## Bundle Location

Each task branch `codex/TASK_XXX` must include evidence at:

```
docs/dev/evidence/<TASK_ID>/
```

Example: `docs/dev/evidence/TASK_061/`

---

## Required Files

Each evidence bundle must contain these files:

| File | Purpose |
|---|---|
| `SUMMARY.md` | Brief summary of what was done, why, and outcome |
| `DIFFSTAT.txt` | Output of `git diff --stat` showing changed files |
| `DIFF.patch` | Full unified diff of all changes |
| `TESTS.txt` | Test execution output or test plan verification |
| `RISK.md` | Risk assessment: what could break, mitigation, rollback |

---

## Generation Commands

Codex must run these commands from the task branch before finalizing:

```bash
# Ensure evidence directory exists
TASK_ID="TASK_XXX"  # Replace with actual task ID
mkdir -p docs/dev/evidence/$TASK_ID

# Generate DIFFSTAT.txt
git diff --stat origin/main...HEAD > docs/dev/evidence/$TASK_ID/DIFFSTAT.txt

# Generate DIFF.patch
git diff origin/main...HEAD > docs/dev/evidence/$TASK_ID/DIFF.patch

# Generate TESTS.txt (run tests and capture output)
# Adapt command to project's test framework
pytest -v > docs/dev/evidence/$TASK_ID/TESTS.txt 2>&1 || true
# OR if no tests, document why:
echo "No automated tests for this task. Manual verification: ..." > docs/dev/evidence/$TASK_ID/TESTS.txt

# Manually create SUMMARY.md
cat > docs/dev/evidence/$TASK_ID/SUMMARY.md <<'SUMMARY'
# Task Summary: TASK_XXX

## What
[Brief description of changes]

## Why
[Rationale, references to planning docs]

## Outcome
[Result: success, partial, blocked, etc.]

## Follow-up
[Any follow-up tasks or notes]
SUMMARY

# Manually create RISK.md
cat > docs/dev/evidence/$TASK_ID/RISK.md <<'RISK'
# Risk Assessment: TASK_XXX

## What Could Break
- [Potential failure modes]

## Mitigation
- [How risks are addressed]

## Rollback Plan
- [How to revert if needed]

## Dependencies
- [External dependencies or assumptions]
RISK
```

---

## ASSIGNMENTS.md Rules

**CRITICAL**: Codex branches must **NEVER** modify `docs/dev/ASSIGNMENTS.md`.

- Cecil is the sole writer to ASSIGNMENTS.md on `main`.
- Cecil updates ASSIGNMENTS.md at merge time only.
- CI will fail any codex/* branch that touches ASSIGNMENTS.md.

---

## Verification

Before pushing, Codex should verify the branch:

```bash
system/scripts/verify-branch.sh codex/TASK_XXX
```

This checks:
- Evidence bundle exists and is complete
- ASSIGNMENTS.md not modified
- Branch naming follows convention

Exit code 0 = PASS, ready to merge.

---

## Merge Process

1. Codex pushes task branch with evidence bundle
2. Cecil runs `system/scripts/merge-queue.sh`
3. Queue verifies each branch
4. Queue merges passing branches to main
5. Cecil updates ASSIGNMENTS.md at merge time

