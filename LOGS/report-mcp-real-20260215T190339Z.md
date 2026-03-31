# MCP Broker Real Install Report

Timestamp (UTC): 20260215T190339Z

Interpreter:
- python3.12 (Python 3.12.12)

Pinned dependency:
- mcp==1.26.0

Smoke test:
- PASS: MCP smoke (DENY + ALLOW) and runtime chain grew by 2

## Setup
1. Installed Python 3.12 via Homebrew
2. Created venv at mcp/.venv
3. Installed mcp SDK (1.26.0)
4. Restored tests/run-mcp-smoke.py with full MCP client integration
5. Successfully ran smoke test with DENY and ALLOW cases

## Result
MCP broker is now fully operational with:
- Policy evaluation via scripts/policy-eval.py
- Decision chain appending to runtime/LOGS/decision-chain.jsonl
- Tamper-evident hash linking
- Full stdio MCP server support
