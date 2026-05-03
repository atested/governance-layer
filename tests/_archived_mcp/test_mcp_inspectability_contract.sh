#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_RUNTIME="$ROOT/out/test_mcp_runtime_contract"
RUN_ID="mcp-rt-003"

rm -rf "$TMP_RUNTIME" "$ROOT/out/mcp_exec/$RUN_ID" "$ROOT/out/mcp_ingest_tool_event/$RUN_ID"
mkdir -p "$TMP_RUNTIME"

export GOV_RUNTIME_DIR="$TMP_RUNTIME"

PYTHONPATH="$ROOT/mcp" python3 - <<'PY'
from pathlib import Path

from capabilities.ingest_tool_event_module import IngestToolEventCapabilityModule
from capability_introspection import emit_action_record
from inspectability_contract import INSPECTABILITY_CONTRACT_VERSION
import server

repo = Path.cwd()
registry = repo / "capabilities" / "capability-registry.json"
run_id = "mcp-rt-003"

module = IngestToolEventCapabilityModule()
params = {
    "tool_event_version": "v0",
    "tool_name": "demo.tool",
    "tool_params_digest": "sha256:" + ("5" * 64),
    "exit_code": 0,
    "outputs": [{"name": "stdout", "digest": "sha256:" + ("6" * 64), "ref_type": "inline"}],
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
replay = server.capabilities_replay_check(run_id)
receipt_links = server.capabilities_receipt_tool_events(run_id)
reverse = server.capabilities_tool_event_receipts(digest)
events_for_receipt = server.capabilities_tool_event_list_for_receipt(run_id)
recent_receipts = server.capabilities_list_recent(10)
recent_events = server.capabilities_tool_event_list_recent(10)
missing_receipt = server.capabilities_receipt("mcp-rt-missing")
missing_replay = server.capabilities_replay_check("mcp-rt-missing")

assert receipt["inspectability_contract"]["version"] == INSPECTABILITY_CONTRACT_VERSION
assert replay["inspectability_contract"]["version"] == INSPECTABILITY_CONTRACT_VERSION
assert receipt_links["inspectability_contract"]["version"] == INSPECTABILITY_CONTRACT_VERSION
assert reverse["inspectability_contract"]["version"] == INSPECTABILITY_CONTRACT_VERSION
assert events_for_receipt["inspectability_contract"]["version"] == INSPECTABILITY_CONTRACT_VERSION

assert receipt["tool_event_digests"] == receipt_links["tool_event_digests"] == [digest]
assert reverse["receipt_ids"] == [run_id]
assert events_for_receipt["events"][0]["tool_event_digest"] == digest
assert events_for_receipt["inspectability_contract"]["query_scope"] == "constitutive"

assert recent_receipts["inspectability_contract"]["query_scope"] == "partial"
assert recent_events["inspectability_contract"]["query_scope"] == "partial"
assert recent_receipts["inspectability_contract"]["query_scope"] != receipt["inspectability_contract"]["query_scope"]
assert missing_receipt["inspectability_contract"]["query_surface"] == "capabilities.receipt"
assert missing_receipt["linked_tool_event_count"] == 0
assert missing_replay["inspectability_contract"]["query_surface"] == "capabilities.replay_check"
assert missing_replay["linked_tool_event_count"] == 0

print("PASS: inspectability contract is explicit, coherent, and distinguishes constitutive from partial query surfaces")
PY

rm -rf "$TMP_RUNTIME" "$ROOT/out/mcp_exec/$RUN_ID" "$ROOT/out/mcp_ingest_tool_event/$RUN_ID"
