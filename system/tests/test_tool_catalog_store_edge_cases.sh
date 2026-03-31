#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_catalog_contract_common.sh"
ROOT="$(tool_catalog_repo_root "${BASH_SOURCE[0]}")"
cd "$ROOT"

TMP_ROOT="out/test_tool_catalog_store_edge_cases"
tool_catalog_reset_dir "$TMP_ROOT"
tool_catalog_reset_catalog_runtime

run_once() {
  local out_file="$1"
  tool_catalog_reset_catalog_runtime
  python3 - "$ROOT" "$out_file" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])
sys.path.insert(0, str(root / "mcp"))
from tool_catalog_store import get, list_recent, put, store_root  # noqa: E402

id1 = put(root, {
    "tool_name": "edge_store_one",
    "tool_version": "1.0.0",
    "schema_json": {"k": 1},
    "declared_capabilities": ["FS_COPY"],
    "created_from": "manual",
})
id2 = put(root, {
    "tool_name": "edge_store_two",
    "tool_version": "1.0.0",
    "schema_json": {"k": 2},
    "declared_capabilities": ["FS_MOVE"],
    "created_from": "external",
})

index_path = store_root(root) / "index.v1.json"
index = json.loads(index_path.read_text(encoding="utf-8"))
index["events"] = [
    {"seq": 2, "tool_id": id2},
    {"seq": 2, "tool_id": id2},  # duplicate event
    {"seq": 1, "tool_id": id1},
    {"seq": 3, "tool_id": "tool_not_hex_chars"},  # invalid tool id
    {"seq": -1, "tool_id": id2},  # invalid seq
    {"seq": 4, "tool_id": ""},  # blank tool id
]
index_path.write_text(json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

recent = list_recent(root, limit=10)
ids = [str(row.get("tool_id", "")) for row in recent]
if ids != [id2, id1]:
    raise SystemExit("FAIL:EDGE_RECENT_ORDER")

if get(root, "tool_not_hex_chars") is not None:
    raise SystemExit("FAIL:INVALID_TOOL_ID_SHOULD_BE_NONE")
if get(root, "../bad") is not None:
    raise SystemExit("FAIL:PATHY_TOOL_ID_SHOULD_BE_NONE")
if get(root, "") is not None:
    raise SystemExit("FAIL:EMPTY_TOOL_ID_SHOULD_BE_NONE")

# Limit parsing should fail closed without throwing and clamp to [1,100].
if len(list_recent(root, limit="not-an-int")) != 2:
    raise SystemExit("FAIL:LIST_LIMIT_INVALID_FALLBACK")
if len(list_recent(root, limit=-5)) != 1:
    raise SystemExit("FAIL:LIST_LIMIT_NEGATIVE_CLAMP")
if len(list_recent(root, limit=9999)) != 2:
    raise SystemExit("FAIL:LIST_LIMIT_UPPER_CLAMP")

# Malformed tool docs should be skipped by list_recent instead of crashing queries.
bad_path = store_root(root) / "tools" / f"{id1}.json"
bad_path.write_text("{bad-json}\n", encoding="utf-8")
recent_after_bad = list_recent(root, limit=10)
ids_after_bad = [str(row.get("tool_id", "")) for row in recent_after_bad]
if ids_after_bad != [id2]:
    raise SystemExit("FAIL:LIST_RECENT_SKIP_MALFORMED")

# Valid JSON with mismatched schema hash must fail closed.
bad_schema_doc_path = store_root(root) / "tools" / f"{id2}.json"
bad_schema_doc = json.loads(bad_schema_doc_path.read_text(encoding="utf-8"))
bad_schema_doc["schema_sha256"] = "0" * 64
bad_schema_doc_path.write_text(json.dumps(bad_schema_doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
try:
    _ = get(root, id2)
except ValueError as exc:
    if str(exc) != "TOOL_DOC_INVALID":
        raise
else:
    raise SystemExit("FAIL:GET_BAD_SCHEMA_SHA_SHOULD_FAIL")
recent_after_bad_schema = list_recent(root, limit=10)
if recent_after_bad_schema:
    raise SystemExit("FAIL:LIST_RECENT_SKIP_BAD_SCHEMA_SHA")

summary = {
    "recent_tool_ids": ids,
    "recent_after_bad": ids_after_bad,
    "recent_after_bad_schema": [str(row.get("tool_id", "")) for row in recent_after_bad_schema],
    "invalid_get_none": True,
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$TMP_ROOT/run1.json"
R2="$TMP_ROOT/run2.json"
run_once "$R1"
run_once "$R2"

H1="$(tool_catalog_sha256_file "$R1")"
H2="$(tool_catalog_sha256_file "$R2")"
tool_catalog_require_equal "$H1" "$H2" "FAIL:NON_DETERMINISTIC"

echo "TOOL_CATALOG_STORE_EDGE_CASES=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
