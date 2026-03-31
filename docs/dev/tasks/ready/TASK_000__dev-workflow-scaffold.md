# TASK_000__dev-workflow-scaffold.md

TASK_ID: TASK_000
Title: Dev workflow scaffold + commit planner snapshot directory
Executor: Cecil
Owner/Gate: Greg
Branch: feat/dev-workflow-scaffold-000
Status: In Progress → Completed
Dependencies: none

## Goal
Turn `docs/dev/` into tracked repo state and establish the deterministic workflow spine:
WORK_QUEUE, TASK_TEMPLATE, ASSIGNMENTS, MERGE_GATE, plus task directories.

## Non-goals
- No changes to any code, scripts, routing, or MCP logic.
- No changes outside `/docs/dev/**`.

## Files allowed to touch
- `/docs/dev/**`

## Files forbidden to touch
- Everything outside `/docs/dev/**`

## Procedure
See parent task specification. Abbreviated:
1. Precondition check (branch=main, working tree clean except docs/dev/)
2. `git checkout -b feat/dev-workflow-scaffold-000`
3. Create `ASSIGNMENTS.md`, claim commit (`chore(assign): claim TASK_000`)
4. Verify `PLANNER_SNAPSHOT.md` in place
5. Create `WORK_QUEUE.md`, `TASK_TEMPLATE.md`, `MERGE_GATE.md`
6. Create `tasks/ready/`, `tasks/blocked/`, `tasks/done/`
7. Seed stubs: TASK_001, TASK_002, TASK_003
8. Update `ASSIGNMENTS.md` to complete; complete commit (`chore(assign): complete TASK_000`)
9. Remaining docs commit (`docs(dev): add workflow spine`)

## Acceptance criteria
- [ ] `docs/dev/` tracked and contains all required files
- [ ] Claim commit is first; complete commit is last
- [ ] Only `docs/dev/**` modified
- [ ] ASSIGNMENTS Active → History migration complete
