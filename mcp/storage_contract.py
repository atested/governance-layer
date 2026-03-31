from __future__ import annotations

import os
from pathlib import Path
from typing import Any


STORAGE_CONTRACT_VERSION = "govmcp_storage_contract_v1"
DEFAULT_RUNTIME_ROOT_RELPATH = ".gov_runtime"


def runtime_root(repo_root: Path) -> Path:
    raw = str(os.environ.get("GOV_RUNTIME_DIR", "")).strip()
    if raw:
        return Path(raw).resolve()
    return (repo_root / DEFAULT_RUNTIME_ROOT_RELPATH).resolve()


def receipt_store_root(repo_root: Path) -> Path:
    return repo_root / "out" / "mcp_exec"


def receipt_run_root(repo_root: Path, run_id: str) -> Path:
    return receipt_store_root(repo_root) / str(run_id)


def receipt_index_path(repo_root: Path) -> Path:
    return receipt_store_root(repo_root) / "index.v1.json"


def tool_event_store_root(repo_root: Path) -> Path:
    return runtime_root(repo_root) / "TOOL_EVENTS"


def tool_event_bundle_store_root(repo_root: Path) -> Path:
    return tool_event_store_root(repo_root) / "BUNDLES"


def tool_event_link_index_path(repo_root: Path) -> Path:
    return receipt_store_root(repo_root) / "tool_event_links.v1.json"


def tool_catalog_store_root(repo_root: Path) -> Path:
    return repo_root / "out" / "mcp_tool_catalog"


def describe_storage_contract(repo_root: Path) -> dict[str, Any]:
    runtime = runtime_root(repo_root)
    return {
        "version": STORAGE_CONTRACT_VERSION,
        "runtime_root": str(runtime).replace("\\", "/"),
        "runtime_root_source": "env:GOV_RUNTIME_DIR" if os.environ.get("GOV_RUNTIME_DIR") else "repo_default:.gov_runtime",
        "receipt_store_root": str(receipt_store_root(repo_root)).replace("\\", "/"),
        "receipt_index_path": str(receipt_index_path(repo_root)).replace("\\", "/"),
        "tool_event_store_root": str(tool_event_store_root(repo_root)).replace("\\", "/"),
        "tool_event_link_index_path": str(tool_event_link_index_path(repo_root)).replace("\\", "/"),
        "tool_catalog_store_root": str(tool_catalog_store_root(repo_root)).replace("\\", "/"),
        "authoritative_artifacts": {
            "receipts": "out/mcp_exec",
            "receipt_tool_event_links": "out/mcp_exec/tool_event_links.v1.json",
            "tool_events": "$GOV_RUNTIME_DIR/TOOL_EVENTS",
            "tool_event_bundles": "$GOV_RUNTIME_DIR/TOOL_EVENTS/BUNDLES",
            "tool_catalog": "out/mcp_tool_catalog",
        },
    }
