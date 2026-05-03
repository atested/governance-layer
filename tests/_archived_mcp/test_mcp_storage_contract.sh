#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

unset GOV_RUNTIME_DIR || true

PYTHONPATH="$ROOT/mcp" python3 - <<'PY'
from pathlib import Path

from storage_contract import (
    DEFAULT_RUNTIME_ROOT_RELPATH,
    STORAGE_CONTRACT_VERSION,
    describe_storage_contract,
    receipt_index_path,
    receipt_store_root,
    runtime_root,
    tool_catalog_store_root,
    tool_event_link_index_path,
    tool_event_store_root,
)
from tool_event_store import runtime_root as store_runtime_root

repo = Path.cwd()
contract = describe_storage_contract(repo)

expected_runtime = (repo / DEFAULT_RUNTIME_ROOT_RELPATH).resolve()
assert runtime_root(repo) == expected_runtime
assert store_runtime_root(repo) == expected_runtime
assert receipt_store_root(repo) == repo / "out" / "mcp_exec"
assert receipt_index_path(repo) == repo / "out" / "mcp_exec" / "index.v1.json"
assert tool_event_link_index_path(repo) == repo / "out" / "mcp_exec" / "tool_event_links.v1.json"
assert tool_event_store_root(repo) == expected_runtime / "TOOL_EVENTS"
assert tool_catalog_store_root(repo) == repo / "out" / "mcp_tool_catalog"
assert contract["version"] == STORAGE_CONTRACT_VERSION
assert contract["runtime_root_source"] == "repo_default:gov_runtime"
assert contract["authoritative_artifacts"]["receipts"] == "out/mcp_exec"
assert contract["authoritative_artifacts"]["tool_events"] == "$GOV_RUNTIME_DIR/TOOL_EVENTS"
print("PASS: GovMCP storage contract defaults and roots are explicit")
PY
