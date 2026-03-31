#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_RUNTIME="$ROOT/out/test_mcp_runtime_exposure"
RUN_ID="mcp-rt-002"

rm -rf "$TMP_RUNTIME" "$ROOT/out/mcp_exec/$RUN_ID" "$ROOT/out/mcp_ingest_tool_event/$RUN_ID"
mkdir -p "$TMP_RUNTIME"

export GOV_RUNTIME_DIR="$TMP_RUNTIME"

PYTHONPATH="$ROOT/mcp" python3 - <<'PY'
from pathlib import Path

from capabilities.ingest_tool_event_module import IngestToolEventCapabilityModule
from capability_introspection import emit_action_record
import server

repo = Path.cwd()
registry = repo / "capabilities" / "capability-registry.json"
run_id = "mcp-rt-002"

module = IngestToolEventCapabilityModule()
params = {
    "tool_event_version": "v0",
    "tool_name": "demo.tool",
    "tool_params_digest": "sha256:" + ("3" * 64),
    "exit_code": 0,
    "outputs": [{"name": "stdout", "digest": "sha256:" + ("4" * 64), "ref_type": "inline"}],
    "policy_context_used": "DEFAULT",
    "provenance": {"source_identifier": "unit-test", "extraction_date": "2026-03-16"},
}
result = module.execute(registry, repo, params, dry_run=False, run_id=run_id)
digest = result["ingest_result"]["tool_event_sha256"]
emit_action_record(
    repo,
    run_id,
    "INGEST_TOOL_EVENT",
    result["normalized_params"],
    "EXECUTED",
    "OK",
    {"executed": True, "admissible": True},
    tool_event_digests=[digest],
)

receipt = server.capabilities_receipt(run_id)
assert receipt["tool_event_digests"] == [digest], receipt
assert receipt["linked_tool_event_count"] == 1, receipt
assert receipt["inspectability_contract"]["query_surface"] == "capabilities.receipt", receipt
assert receipt["storage_contract"]["authoritative_artifacts"]["receipts"] == "out/mcp_exec", receipt

replay = server.capabilities_replay_check(run_id)
assert replay["admissible_now"] is True, replay
assert replay["tool_event_digests"] == [digest], replay
assert replay["linked_tool_event_count"] == 1, replay
assert replay["storage_contract"]["authoritative_artifacts"]["tool_events"] == "$GOV_RUNTIME_DIR/TOOL_EVENTS", replay

receipt_links = server.capabilities_receipt_tool_events(run_id)
assert receipt_links["tool_event_digests"] == [digest], receipt_links
assert receipt_links["linked_tool_event_count"] == 1, receipt_links
assert receipt_links["inspectability_contract"]["query_scope"] == "constitutive", receipt_links
assert receipt_links["storage_contract"]["version"] == "govmcp_storage_contract_v1", receipt_links

reverse = server.capabilities_tool_event_receipts(digest)
assert reverse["receipt_ids"] == [run_id], reverse
assert reverse["linked_receipt_count"] == 1, reverse

rows = server.capabilities_tool_event_list_for_receipt(run_id)
assert len(rows["events"]) == 1, rows
assert rows["events"][0]["tool_event_digest"] == digest, rows
assert rows["events"][0]["resolution_state"] == "RESOLVED", rows
assert rows["linked_tool_event_count"] == 1, rows
assert rows["storage_contract"]["receipt_store_root"].endswith("/out/mcp_exec"), rows

recent = server.capabilities_list_recent(10)
assert recent["inspectability_contract"]["query_scope"] == "partial", recent

event_recent = server.capabilities_tool_event_list_recent(10)
assert event_recent["inspectability_contract"]["query_scope"] == "partial", event_recent
print("PASS: MCP exposure layer is aligned to the canonical storage and continuity contract")
PY

rm -rf "$TMP_RUNTIME" "$ROOT/out/mcp_exec/$RUN_ID" "$ROOT/out/mcp_ingest_tool_event/$RUN_ID"
