# Agents and Ops Process

This repository uses a dispatch-driven multi-agent workflow.

## Active Agents

- **Greg**: Human product owner and source of intent
- **Tier 0** (Claude.ai Max + AutoOn): Strategic orchestrator. Produces formal dispatches. Reviews results. Never writes code.
- **Cowork** (transport tier): Carries dispatches and results between Tier 0 and Cecil. Does not think or make decisions.
- **Cecil** (Claude Code, Opus): Strategic lead, sole merger to main, primary builder. Receives dispatches, executes work, reports results.
- **Sonnet-worker** (subagent within Cecil, Sonnet): Test verification, merge mechanics, structured validation. Escalates to Cecil for judgment calls.
- **Lq** (Little Queen, qwen2.5:7b-instruct via Ollama): Classification, tagging, preprocessing, drafting. Supervised collaborator.
- **Qt** (Queen of Tests, qwen2.5:7b-instruct via Ollama): QA-specific mechanical work and adversarial auditing. Supervised collaborator.
- **Bq** (Big Queen, larger context model via Ollama): Extended-context tasks. Supervised collaborator.

## Shelved Agents

- **Codex** (Codex CLI): Throughput engine, formerly autonomous task executor. Shelved as of ops process v2. Build functions absorbed by Cecil. Test functions absorbed by Sonnet-worker and Qt. May return.
- **ChatGPT**: Formerly orchestrator and batch architect. Role superseded by Tier 0 dispatch model.

## Ops Process

For detailed collaboration rules, roles, and procedures, read:

**[docs/dev/OPS_PROCESS__DISPATCH_CECIL__v2.md](docs/dev/OPS_PROCESS__DISPATCH_CECIL__v2.md)** (current)

**[docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md](docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md)** (historical reference)

## Quick Reference

- **Greg**: Provide goals, acceptance criteria, authorize merge windows
- **Tier 0**: Plan with Greg, produce dispatches, review results, approve merges
- **Cowork**: Deliver dispatches to Cecil, deliver results to Tier 0
- **Cecil**: Execute dispatches, merge to main, maintain architectural integrity
- **Sonnet-worker**: Test execution, merge mechanics, verification (within Cecil's session)
- **Sisters (Lq, Qt, Bq)**: Supervised mechanical work at zero API cost

For the complete ops process including dispatch format, merge strategies, evidence contracts, and system-wide constraints, see the ops process doc above.
