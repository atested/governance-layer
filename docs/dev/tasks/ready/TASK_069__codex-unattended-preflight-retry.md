# TASK_069__codex-unattended-preflight-retry.md

TASK_ID: TASK_069
Title: Harden codex-unattended preflight for intermittent DNS/SSH
Executor: UNASSIGNED
Status: Ready
Dependencies: none

## Goal
Reduce false unattended halts from transient DNS/SSH failures by adding deterministic retries in `system/scripts/codex-unattended.sh` while preserving fail-closed behavior.

## Constraints
- Do not merge to main.
- Do not edit WORK_QUEUE.md.
- Do not edit docs/dev/ASSIGNMENTS.md.
- Do not call/use merge-queue.sh.
- Deterministic outputs only (no timestamps/randomized backoff).
- Fail closed after retry budget is exhausted.

## Required changes
1) DNS preflight gate retry:
- 5 attempts
- 2 second fixed sleep between attempts
- use embedded Python with `socket.gethostbyname("github.com")`
- on success, print:
  - `OK: DNS github.com -> <ip> (attempt X/5)`
- on final failure, print:
  - `ERROR: DNS gate failed after 5 attempts`
  - last Python exception text
  - diagnostics: `scutil --dns | sed -n '1,160p' || true`
- exit nonzero

2) SSH preflight gate retry:
- 3 attempts
- 2 second fixed sleep
- `ssh -T git@github.com` success when output indicates successful authentication
- on success, print:
  - `OK: SSH auth ok (attempt X/3)`
- on final failure, print:
  - `ERROR: SSH gate failed after 3 attempts`
  - last ssh stderr text
- exit nonzero

3) Side effects:
- no additional files written by preflight beyond existing `.git/index.lock` probe behavior
- keep preflight otherwise read-only

## Files allowed to touch
- system/scripts/codex-unattended.sh
- docs/dev/tasks/ready/TASK_069__codex-unattended-preflight-retry.md
- docs/dev/evidence/TASK_069/**
- docs/dev/inventory/INVENTORY_LATEST.md

## Files forbidden to touch
Everything else.

## Test plan / evidence required
Create `docs/dev/evidence/TASK_069/TESTS.txt` with full output for:
- `bash system/scripts/codex-unattended.sh preflight`
- `bash -n system/scripts/codex-unattended.sh`
- Optional but recommended: `python3 scripts/verify-ops-canonical.py`

Notes:
- Forcing a DNS failure is not required.
- If environment still fails DNS/SSH after retries, evidence must show retry behavior and fail-closed result.

## Acceptance criteria
- Script parses with `bash -n`.
- Preflight uses deterministic retry counts and sleep intervals for DNS and SSH gates.
- On persistent failure, script exits nonzero and prints required diagnostics.
