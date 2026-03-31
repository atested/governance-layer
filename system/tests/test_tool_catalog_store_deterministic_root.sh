#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_catalog_contract_common.sh"
ROOT="$(tool_catalog_repo_root "${BASH_SOURCE[0]}")"
cd "$ROOT"

TMP_ROOT="out/test_tool_catalog_store_deterministic_root"
rm -rf "$TMP_ROOT" out/mcp_tool_catalog
mkdir -p "$TMP_ROOT"

run_once() {
  local out_file="$1"
  rm -rf out/mcp_tool_catalog
  python3 - "$ROOT" "$out_file" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])
sys.path.insert(0, str(root / "mcp"))

from tool_catalog_store import put, store_root  # noqa: E402

repo_root = root
tool_doc = {
    "tool_name": "store_root_probe",
    "tool_version": "0.0.1",
    "schema_json": {"kind": "probe", "version": 1},
    "declared_capabilities": ["FS_MOVE", "FS_COPY"],
    "created_from": "manual",
}
tool_id = put(repo_root, tool_doc)
idx_path = store_root(repo_root) / "index.v1.json"
idx = json.loads(idx_path.read_text(encoding="utf-8"))
summary = {
    "store_root_rel": str(store_root(repo_root).relative_to(repo_root)).replace("\\", "/"),
    "tool_id": tool_id,
    "index_version": idx.get("index_version"),
    "next_seq": idx.get("next_seq"),
    "events": idx.get("events"),
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$TMP_ROOT/run1.json"
R2="$TMP_ROOT/run2.json"
run_once "$R1"
run_once "$R2"

python3 - "$R1" <<'PY'
import json
import sys
obj = json.load(open(sys.argv[1], encoding="utf-8"))
if obj.get("store_root_rel") != "out/mcp_tool_catalog":
    raise SystemExit("FAIL:STORE_ROOT")
if obj.get("index_version") != "tool_catalog_index_v1":
    raise SystemExit("FAIL:INDEX_VERSION")
if not isinstance(obj.get("events"), list) or len(obj["events"]) != 1:
    raise SystemExit("FAIL:EVENTS")
if obj["events"][0].get("seq") != 1:
    raise SystemExit("FAIL:SEQ")
PY

H1="$(tool_catalog_sha256_file "$R1")"
H2="$(tool_catalog_sha256_file "$R2")"
tool_catalog_require_equal "$H1" "$H2" "FAIL:NON_DETERMINISTIC"

echo "TOOL_CATALOG_STORE_DETERMINISTIC_ROOT=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
