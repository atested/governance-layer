#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_tool_event_store_edge_cases"
OUT_DIR="out/test_tool_event_store_edge_cases_out"
RUNTIME_DIR="$TMP_ROOT/runtime"
rm -rf "$TMP_ROOT" "$OUT_DIR"
mkdir -p "$TMP_ROOT" "$OUT_DIR"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT"
  mkdir -p "$TMP_ROOT"

  GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 - "$ROOT" "$out_file" "$RUNTIME_DIR" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])
runtime = pathlib.Path(sys.argv[3])

sys.path.insert(0, str(root / "mcp"))
import tool_event_store as store

# Seed with valid entries through supported APIs.
d1 = "sha256:" + "1" * 64
d2 = "sha256:" + "2" * 64
row1 = store.upsert_tool_event_index(root, "RID_EDGE_1", d1, "runtime/TOOL_EVENTS/tool_event_1.json", "runtime/RECEIPTS/action_1.json")
row2 = store.upsert_tool_event_index(root, "RID_EDGE_2", d2, "runtime/TOOL_EVENTS/tool_event_2.json", "runtime/RECEIPTS/action_2.json")
if int(row1.get("stored_seq", 0)) < 1 or int(row2.get("stored_seq", 0)) < 1:
    raise SystemExit("FAIL:UPSERT_SEQ")

store.upsert_tool_event_bundle(root, "teb_" + "a" * 64, "sha256:" + "b" * 64, 2, "runtime/TOOL_EVENTS/BUNDLES/teb_a")

# Corrupt index with malformed but parseable entries; loader must fail closed.
index_path = runtime / "TOOL_EVENTS" / "index.v1.json"
index = json.loads(index_path.read_text(encoding="utf-8"))
index["entries"].extend(
    [
        {
            "receipt_id": "RID_BAD",
            "run_id": "RID_BAD",
            "stored_seq": 999,
            "tool_event_digest": "sha256:not-a-digest",
            "tool_event_ref": "runtime/TOOL_EVENTS/bad.json",
            "action_record_ref": "runtime/RECEIPTS/bad.json",
        },
        {
            "receipt_id": "RID_EDGE_1",
            "run_id": "RID_EDGE_1",
            "stored_seq": 998,
            "tool_event_digest": d1,
            "tool_event_ref": "../escape.json",
            "action_record_ref": "runtime/RECEIPTS/action_1.json",
        },
        {
            "receipt_id": "bad receipt id",
            "run_id": "bad receipt id",
            "stored_seq": 997,
            "tool_event_digest": d2,
            "tool_event_ref": "runtime/TOOL_EVENTS/tool_event_2.json",
            "action_record_ref": "runtime/RECEIPTS/action_2.json",
        },
        {
            "receipt_id": "RID_EDGE_2",
            "run_id": "RID_EDGE_2",
            "stored_seq": 996,
            "tool_event_digest": d2,
            "tool_event_ref": "runtime/TOOL_EVENTS/tool_event_2.json",
            "action_record_ref": "runtime/RECEIPTS/action_2.json",
        },
    ]
)
index_path.write_text(json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

entries = store.list_all_tool_events(root)
if [e.get("run_id") for e in entries] != ["RID_EDGE_1", "RID_EDGE_2"]:
    raise SystemExit("FAIL:ENTRY_NORMALIZE")
if [int(e.get("stored_seq", 0)) for e in entries] != [1, 2]:
    raise SystemExit("FAIL:ENTRY_RESEQUENCE")

if store.get_tool_event_by_digest(root, "sha256:not-a-digest") is not None:
    raise SystemExit("FAIL:BAD_DIGEST_NONE")
if store.get_tool_event_by_digest(root, d2) is None:
    raise SystemExit("FAIL:GET_VALID_DIGEST")

if len(store.list_tool_events_recent(root, "bad-limit")) != 2:  # type: ignore[arg-type]
    raise SystemExit("FAIL:LIMIT_FALLBACK")
if len(store.list_tool_events_recent(root, -1)) != 1:
    raise SystemExit("FAIL:LIMIT_CLAMP_MIN")
if len(store.list_tool_events_recent(root, 1000)) != 2:
    raise SystemExit("FAIL:LIMIT_CLAMP_MAX")

# Corrupt bundle index with malformed entries; bundle loader must fail closed.
bundle_idx = runtime / "TOOL_EVENTS" / "BUNDLES" / "index.v1.json"
bdoc = json.loads(bundle_idx.read_text(encoding="utf-8"))
bdoc["entries"].extend(
    [
        {
            "bundle_id": "teb_not_hex",
            "manifest_sha256": "sha256:" + "c" * 64,
            "tool_event_digests_count": 1,
            "bundle_ref": "runtime/TOOL_EVENTS/BUNDLES/teb_bad",
            "stored_seq": 8,
        },
        {
            "bundle_id": "teb_" + "a" * 64,
            "manifest_sha256": "sha256:not-a-digest",
            "tool_event_digests_count": -1,
            "bundle_ref": "../bad",
            "stored_seq": 7,
        },
    ]
)
bundle_idx.write_text(json.dumps(bdoc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

if store.get_tool_event_bundle(root, "teb_not_hex") is not None:
    raise SystemExit("FAIL:BAD_BUNDLE_ID_NONE")
valid_bundle = store.get_tool_event_bundle(root, "teb_" + "a" * 64)
if not isinstance(valid_bundle, dict):
    raise SystemExit("FAIL:VALID_BUNDLE_MISSING")
if int(valid_bundle.get("stored_seq", 0)) != 1:
    raise SystemExit("FAIL:BUNDLE_RESEQUENCE")

summary = {
    "runs": [e.get("run_id") for e in entries],
    "stored_seq": [int(e.get("stored_seq", 0)) for e in entries],
    "bundle_id": str(valid_bundle.get("bundle_id", "")),
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$OUT_DIR/run1.json"
R2="$OUT_DIR/run2.json"
run_once "$R1"
run_once "$R2"

H1="$(shasum -a 256 "$R1" | awk '{print $1}')"
H2="$(shasum -a 256 "$R2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "TOOL_EVENT_STORE_EDGE_CASES=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
