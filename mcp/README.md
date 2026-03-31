# Governance MCP Broker (Phase 1)

This is a general-purpose MCP server that exposes governed tools (starting with `fs_write`).
It is **not OpenClaw-specific**. Any MCP client can connect.

## Runtime evidence (outside repo)
Default runtime directory:
- /Volumes/SSD/archive/gov/runtime
Chain:
- /Volumes/SSD/archive/gov/runtime/LOGS/decision-chain.jsonl

Override with:
- GOV_RUNTIME_DIR=/path/to/runtime

## Install
Recommended:
- python3 -m venv .venv && source .venv/bin/activate
- python3 -m pip install -r mcp/requirements.txt

## Run (stdio)
- GOV_RUNTIME_DIR=/Volumes/SSD/archive/gov/runtime python3 mcp/server.py

## Tools
- fs_write: governed file write
