# Universal Dev Process Manifest v1

**Scope:** This manifest covers only universal dev-process files transplanted unchanged under the accepted bootstrap protocol canon. It does not cover repo-local stubs. It does not cover application-governance substrate.

**Inclusion rule reference:** This manifest is derived mechanically from `docs/dev/NEW_PROJECT_BOOTSTRAP_PROTOCOL__v1.md` Section 1.6 on `origin/main` at `dc77ceba344bb9a455cea7ecc38b55947fb30138`. This document does not re-decide universality.

**Exclusion note:** Repo-local files, stub templates, activation scripts, and application-specific governance surfaces are out of scope. `.claude/commands/cecil.md` is excluded because the controlling canon explicitly classifies it as repo-local, not universal.

| Canonical file name | Source path in governance-layer | Destination path in new project | Transplant mode | Short purpose statement | Version identifier | Notes |
|---|---|---|---|---|---|---|
| OPS_PROCESS | `docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md` | `docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md` | copy unchanged | Role definitions, collaboration loop, task/merge/evidence rules | `v1` | |
| AGENT_CONTRACT | `docs/dev/AGENT_CONTRACT.md` | `docs/dev/AGENT_CONTRACT.md` | copy unchanged | Agent confirmation policy and safe defaults | — | |
| BRIEFING_FORMAT | `docs/dev/BRIEFING_FORMAT__BFPS_v12.md` | `docs/dev/BRIEFING_FORMAT__BFPS_v12.md` | copy unchanged | Session ingestion and handoff format | `v12` | |
| TASK_TEMPLATE | `docs/dev/TASK_TEMPLATE.md` | `docs/dev/TASK_TEMPLATE.md` | copy unchanged | Standard task specification template | — | |
| INGESTION_WORKFLOW | `docs/dev/INGESTION_WORKFLOW.md` | `docs/dev/INGESTION_WORKFLOW.md` | copy unchanged | Workflow for ingesting external content | — | |
| RUNBOOK | `docs/dev/RUNBOOK.md` | `docs/dev/RUNBOOK.md` | copy unchanged | Session-start protocol and lane definitions | — | |
| haiku-worker | `.claude/agents/haiku-worker.md` | `.claude/agents/haiku-worker.md` | copy unchanged | Haiku-tier subordinate agent definition | — | Source and destination are repo-root relative, not under `docs/dev/` |
| sonnet-worker | `.claude/agents/sonnet-worker.md` | `.claude/agents/sonnet-worker.md` | copy unchanged | Sonnet-tier subordinate agent definition | — | Source and destination are repo-root relative, not under `docs/dev/` |
