# Agents and Ops Process

This repository uses a multi-agent workflow involving:
- **ChatGPT**: Orchestrator and batch architect
- **Codex**: Throughput engine (autonomous task executor)
- **Cecil**: Strategic lead and high-stakes operator (merges, conflicts, architecture)
- **Greg**: Human product owner and source of intent

## Ops Process

For detailed collaboration rules, roles, and procedures, read:

**[docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md](docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md)**

This document is automatically loaded and prepended to every Codex execution run.

## Quick Reference

- **Codex role**: Execute task specs within allowlists, emit evidence, push branches
- **Cecil role**: Merge to main, resolve conflicts, maintain architectural integrity
- **ChatGPT role**: Turn Greg's intent into Codex dispatches, decide merge windows
- **Greg role**: Provide goals, acceptance criteria, authorize merge windows

For the complete ops process including hot files, merge strategies, evidence contracts, and dispatch templates, see the ops process doc above.
