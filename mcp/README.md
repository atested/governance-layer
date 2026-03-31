# Governance MCP Broker (Phase 1)

This is a general-purpose MCP server that exposes governed tools (starting with `fs_write`).
It is **not OpenClaw-specific**. Any MCP client can connect.

## Runtime evidence (outside repo)
Runtime directory semantics:
- Set `GOV_RUNTIME_DIR=/absolute/path` to choose the runtime root explicitly.
- If unset, the MCP server currently defaults to `/Volumes/SSD/archive/gov/runtime`.

Runtime layout under `$GOV_RUNTIME_DIR`:
- `LOGS/decision-chain.jsonl` (append-only decision chain)
- `LOGS/intents/` (captured normalized intents)
- `LOGS/records/` (decision records)
- `LOGS/quarantine/` (quarantined broken chains + reason files)

## Install
Canonical venv location for this repo:
- mcp/.venv

Canonical interpreter for MCP smoke/tests:
- mcp/.venv/bin/python3

Create it from repo root:
- python3 -m venv mcp/.venv
- mcp/.venv/bin/python3 -m pip install -r mcp/requirements.txt

## Dependency pin note (`mcp==1.26.0`)
- Pin location: `mcp/requirements.txt` (`mcp==1.26.0`).
- Rationale: keep MCP client/server behavior deterministic across local runs and CI by using one known-good SDK version.
- Safe update procedure:
  1. Change only `mcp/requirements.txt` to the target version.
  2. Recreate or update the venv and reinstall dependencies.
  3. Run repo smoke/tests that exercise MCP paths (at minimum `tests/run-mcp-smoke.sh`).
  4. Document the version change and verification evidence in the task/PR.

## Smoke test (repo root, no manual venv activation)
- tests/run-mcp-smoke.sh

## Run (stdio)
- GOV_RUNTIME_DIR=/Volumes/SSD/archive/gov/runtime mcp/.venv/bin/python3 mcp/server.py
- GOV_RUNTIME_DIR=/path/to/runtime python3 mcp/server.py

## Tools
- fs_write: governed file write
