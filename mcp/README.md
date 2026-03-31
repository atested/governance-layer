# Governance MCP Broker (Phase 1)

This is a general-purpose MCP server that exposes governed tools (starting with `fs_write`).
It is **not OpenClaw-specific**. Any MCP client can connect.

## Runtime evidence (outside repo)
Runtime directory semantics:
- Set `GOV_RUNTIME_DIR=/absolute/path` to choose the runtime root explicitly.
- If unset, GovMCP now defaults to the repo-local runtime root `.gov_runtime/`.
- The GovMCP required-path storage contract is intentionally multi-root:
  - receipts and receipt-to-tool-event link indexes are authoritative under `out/mcp_exec/`
  - tool-event indexes and bundles are authoritative under `$GOV_RUNTIME_DIR/TOOL_EVENTS/`
  - tool-catalog state remains supporting and authoritative under `out/mcp_tool_catalog/`

Runtime layout under `$GOV_RUNTIME_DIR`:
- `LOGS/decision-chain.jsonl` (append-only decision chain)
- `LOGS/intents/` (captured normalized intents)
- `LOGS/records/` (decision records)
- `LOGS/quarantine/` (quarantined broken chains + reason files)
- `TOOL_EVENTS/index.v1.json` (authoritative tool-event index for GovMCP required-path continuity)
- `TOOL_EVENTS/BUNDLES/` (tool-event bundle store)

Required-path state under `out/`:
- `out/mcp_exec/index.v1.json` (authoritative receipt index)
- `out/mcp_exec/<run_id>/action_record.json` (authoritative receipt/action record)
- `out/mcp_exec/tool_event_links.v1.json` (receipt-to-tool-event bridge index)
- `out/mcp_tool_catalog/` (supporting tool-catalog store; not a default blocker surface)

## Inspectability Contract

Broader GovMCP maturity beyond the landed minimum required path is bounded around a receipt-linked inspectability/query contract:

- constitutive surfaces:
  - `capabilities.receipt`
  - `capabilities.replay_check`
  - `capabilities.receipt_tool_events`
  - `capabilities.tool_event_receipts`
  - `capabilities.tool_event_list_for_receipt`
- partial surfaces:
  - `capabilities.list_recent`
  - `capabilities.tool_event_list_recent`

This keeps the seam focused on coherent receipt-linked inspection rather than broad connector redesign. Tool-catalog, bundle/export, and generic API cleanup remain supporting unless later evidence proves they are required.

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
- GOV_RUNTIME_DIR=/absolute/path/to/runtime mcp/.venv/bin/python3 mcp/server.py
- GOV_RUNTIME_DIR=/path/to/runtime python3 mcp/server.py
- python3 mcp/server.py  # defaults to repo-local .gov_runtime/

## Run (remote foundation / streamable-http)
Dedicated remote-foundation entrypoint:
- `python3 mcp/remote_server.py`

Minimum runtime/config surface introduced by the remote foundation tranche:
- `GOVMCP_HOST`:
  - default `127.0.0.1`
- `GOVMCP_PORT`:
  - default `8000`
- `GOVMCP_STREAMABLE_HTTP_PATH`:
  - default `/mcp`
- `GOVMCP_LOG_LEVEL`:
  - default `INFO`
- `GOV_RUNTIME_DIR`:
  - same runtime-root contract as local stdio mode

Example local-only remote-foundation run:
- `GOVMCP_HOST=127.0.0.1 GOVMCP_PORT=8000 python3 mcp/remote_server.py`

Remote-foundation scope note:
- transport boundary: `streamable-http`
- auth/access control: not configured in this tranche
- deployment packaging and public exposure hardening: not configured in this tranche

Print the effective remote foundation contract without starting the server:
- `python3 mcp/remote_server.py --print-config`

## Tools
- fs_write: governed file write
