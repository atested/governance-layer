#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_RUNTIME="$ROOT/out/test_mcp_runtime"
RUN_ID="mcp-rt-001"

rm -rf "$TMP_RUNTIME" "$ROOT/out/mcp_exec/$RUN_ID" "$ROOT/out/mcp_ingest_tool_event/$RUN_ID"
mkdir -p "$TMP_RUNTIME"

export GOV_RUNTIME_DIR="$TMP_RUNTIME"

PYTHONPATH="$ROOT/mcp" python3 - <<'PY'
from pathlib import Path

from capabilities.ingest_tool_event_module import IngestToolEventCapabilityModule
from capability_introspection import emit_action_record, list_recent_receipts, load_receipt, replay_check
from inspectability_contract import INSPECTABILITY_CONTRACT_VERSION
from tool_event_link_store import get_receipts_for_tool_event, get_tool_events_for_receipt, upsert_receipt_tool_event_links
from storage_contract import describe_storage_contract

repo = Path.cwd()
registry = repo / "capabilities" / "capability-registry.json"
run_id = "mcp-rt-001"

module = IngestToolEventCapabilityModule()
params = {
    "tool_event_version": "v0",
    "tool_name": "demo.tool",
    "tool_params_digest": "sha256:" + ("1" * 64),
    "exit_code": 0,
    "outputs": [{"name": "stdout", "digest": "sha256:" + ("2" * 64), "ref_type": "inline"}],
    "policy_context_used": "DEFAULT",
    "provenance": {"source_identifier": "unit-test", "extraction_date": "2026-03-16"},
}

result = module.execute(registry, repo, params, dry_run=False, run_id=run_id)
assert result["executed"] is True, result
ingest = result["ingest_result"]
event_digest = ingest["tool_event_sha256"]

receipt = emit_action_record(
    repo,
    run_id,
    "INGEST_TOOL_EVENT",
    result["normalized_params"],
    "EXECUTED",
    "OK",
    {"executed": True, "admissible": True},
    tool_event_digests=[event_digest],
)
assert receipt["digest"].startswith("sha256:")

loaded = load_receipt(repo, run_id)
assert loaded["digest_valid"] is True, loaded
assert loaded["tool_event_digests"] == [event_digest], loaded
assert loaded["linked_tool_event_count"] == 1, loaded
assert loaded["inspectability_contract"]["version"] == INSPECTABILITY_CONTRACT_VERSION, loaded
assert loaded["inspectability_contract"]["query_scope"] == "constitutive", loaded
assert loaded["storage_contract"]["authoritative_artifacts"]["receipt_tool_event_links"] == "out/mcp_exec/tool_event_links.v1.json"

# Continuity must work even before the explicit out/ link index is present.
assert get_tool_events_for_receipt(repo, run_id) == [event_digest]
assert get_receipts_for_tool_event(repo, event_digest) == [run_id]

# And still work once the explicit bridge index is written.
upsert_receipt_tool_event_links(repo, run_id, [event_digest])
assert get_tool_events_for_receipt(repo, run_id) == [event_digest]
assert get_receipts_for_tool_event(repo, event_digest) == [run_id]

replay = replay_check(registry, repo, run_id, emit_artifact=True)
assert replay["admissible_now"] is True, replay
assert replay["tool_event_digests"] == [event_digest], replay
assert replay["linked_tool_event_count"] == 1, replay
assert replay["inspectability_contract"]["query_surface"] == "capabilities.replay_check", replay
assert replay["storage_contract"]["version"] == describe_storage_contract(repo)["version"]
recent = list_recent_receipts(repo, 5)
assert recent["inspectability_contract"]["query_scope"] == "partial", recent
assert recent["receipts"][0]["linked_tool_event_count"] == 1, recent
artifact = repo / "out" / "mcp_exec" / run_id / "replay_check.v0.json"
assert artifact.is_file(), artifact
print("PASS: receipt to tool-event continuity and replay linkage are closed across the mixed-root contract")
PY

rm -rf "$TMP_RUNTIME" "$ROOT/out/mcp_exec/$RUN_ID" "$ROOT/out/mcp_ingest_tool_event/$RUN_ID"
