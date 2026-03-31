# TASK_001__upload-snapshot.md

TASK_ID: TASK_001
Title: Upload PLANNER_SNAPSHOT.md to ChatGPT for batch planning
Executor: Greg
Owner/Gate: Greg
Branch: n/a (manual step; no code changes)
Status: Ready
Dependencies: TASK_000

## Goal
Upload `docs/dev/PLANNER_SNAPSHOT.md` into a ChatGPT session and prompt it to generate
a prioritised batch of task stubs (TASK_004+) covering the next sprint of work.

## Non-goals
- No repo changes in this task.
- No code or config changes.
- No commitment to execute any generated tasks yet.



## Files allowed to touch
- docs/dev/evidence/TASK_001/**

## Files forbidden to touch
- Everything else
## Procedure

Step 1 — Prepare snapshot for upload (read-only)
- Confirm `docs/dev/PLANNER_SNAPSHOT.md` exists and is up to date for planning input.
- Do not run branch-switching or merge commands as part of evidence capture for this task.

Step 2 — Open ChatGPT (or Claude, or another model)
- Start a new conversation.
- Upload or paste the full contents of `docs/dev/PLANNER_SNAPSHOT.md`.

Step 3 — Prompt for batch planning
Use a prompt along these lines:
> "You are a senior engineer reviewing this governance-layer repo snapshot.
> Based on the Open Work / Priorities section and the overall architecture,
> generate 5–10 prioritised task stubs using the TASK_TEMPLATE format.
> Each stub needs: TASK_ID (starting at TASK_004), Title, Goal, Non-goals,
> Files allowed/forbidden, Acceptance criteria. Do not execute — plan only."

Step 4 — Review output
- Check that generated stubs are scoped, bounded, and match project direction.
- Save raw output somewhere (e.g. paste into a local scratchpad or new file).

Step 5 — Hand off to TASK_002
- No repo commit required for this task.
- If recording evidence in-repo, use only docs/dev/evidence/TASK_001/**.

Notes for automation
- This is Greg-owned manual process work; throughput/Codex executors should skip it unless explicitly directed to produce closeout evidence only.

## Acceptance criteria
- [ ] PLANNER_SNAPSHOT.md uploaded/pasted to model successfully
- [ ] Model returned at least 5 task stubs
- [ ] Stubs reviewed for scope and coherence
- [ ] TASK_002 promoted to Next in WORK_QUEUE

## Evidence packet required
- External screenshot/paste of model output (first 2 stubs minimum), or
- docs/dev/evidence/TASK_001/TESTS.txt closeout note summarizing the manual completion
- Confirmation that stubs were reviewed

## Notes
This is a manual human task. No assignment handshake commit needed (no repo change).
