#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_event_receipt_replay_common.sh"
tool_event_receipt_replay_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_tool_event_receipt_negative_matrix"
RESULT_DIR="out/test_tool_event_receipt_negative_matrix_results"
RUNTIME_DIR="$TMP_ROOT/runtime"
tool_event_receipt_replay_reset "$TMP_ROOT" "$RESULT_DIR"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" out/mcp_exec
  mkdir -p "$TMP_ROOT" out/mcp_exec

  python3 - "$ROOT" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
index_path = root / "out" / "mcp_exec" / "tool_event_links.v1.json"
index = {
    "tool_event_link_index_version": "v1",
    "receipt_to_tool_events": [
        {"receipt_id": "RID_Z", "tool_event_digests": ["sha256:" + "b" * 64, "sha256:" + "a" * 64]},
        {"receipt_id": "RID_Z", "tool_event_digests": ["sha256:not-a-digest", "", "sha256:" + "a" * 64]},
        {"receipt_id": "bad receipt id", "tool_event_digests": ["sha256:" + "f" * 64]},
        {"receipt_id": "RID_EMPTY", "tool_event_digests": []},
    ],
    "tool_event_to_receipts": [
        {"tool_event_digest": "sha256:" + "a" * 64, "receipt_ids": ["RID_Z", "bad receipt id", "RID_Z"]},
        {"tool_event_digest": "sha256:not-a-digest", "receipt_ids": ["RID_Z"]},
    ],
}
index_path.write_text(json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY

  GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 - "$ROOT" "$out_file" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])
sys.path.insert(0, str(root / "mcp"))
from tool_event_link_store import get_receipts_for_tool_event, get_tool_events_for_receipt  # noqa: E402

digest_a = "sha256:" + "a" * 64
digest_b = "sha256:" + "b" * 64

forward = get_tool_events_for_receipt(root, "RID_Z")
if forward != [digest_a, digest_b]:
    raise SystemExit("FAIL:FORWARD_SANITIZE")

reverse_a = get_receipts_for_tool_event(root, digest_a)
if reverse_a != ["RID_Z"]:
    raise SystemExit("FAIL:REVERSE_SANITIZE_A")

reverse_b = get_receipts_for_tool_event(root, digest_b)
if reverse_b != ["RID_Z"]:
    raise SystemExit("FAIL:REVERSE_SANITIZE_B")

if get_tool_events_for_receipt(root, "bad receipt id"):
    raise SystemExit("FAIL:MALFORMED_RECEIPT_SHOULD_BE_EMPTY")
if get_receipts_for_tool_event(root, "sha256:not-a-digest"):
    raise SystemExit("FAIL:MALFORMED_DIGEST_SHOULD_BE_EMPTY")
if get_tool_events_for_receipt(root, "RID_MISSING"):
    raise SystemExit("FAIL:MISSING_RECEIPT_SHOULD_BE_EMPTY")

summary = {
    "forward": forward,
    "reverse_a": reverse_a,
    "reverse_b": reverse_b,
}

# Fail-closed on unsupported index version.
index_path = root / "out" / "mcp_exec" / "tool_event_links.v1.json"
index_bad_version = {
    "tool_event_link_index_version": "v0",
    "receipt_to_tool_events": [{"receipt_id": "RID_Z", "tool_event_digests": [digest_a]}],
    "tool_event_to_receipts": [{"tool_event_digest": digest_a, "receipt_ids": ["RID_Z"]}],
}
index_path.write_text(json.dumps(index_bad_version, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
if get_tool_events_for_receipt(root, "RID_Z"):
    raise SystemExit("FAIL:BAD_VERSION_SHOULD_BE_EMPTY")
if get_receipts_for_tool_event(root, digest_a):
    raise SystemExit("FAIL:BAD_VERSION_REVERSE_SHOULD_BE_EMPTY")

# Fail-closed on reverse-only missing-link payloads.
index_reverse_only = {
    "tool_event_link_index_version": "v1",
    "receipt_to_tool_events": [],
    "tool_event_to_receipts": [{"tool_event_digest": digest_a, "receipt_ids": ["RID_Z"]}],
}
index_path.write_text(json.dumps(index_reverse_only, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
if get_receipts_for_tool_event(root, digest_a):
    raise SystemExit("FAIL:REVERSE_ONLY_SHOULD_BE_EMPTY")

summary["bad_version_empty"] = True
summary["reverse_only_empty"] = True

# Fail-closed on malformed top-level shape.
index_bad_shape = {
    "tool_event_link_index_version": "v1",
    "receipt_to_tool_events": {"receipt_id": "RID_Z", "tool_event_digests": [digest_a]},
    "tool_event_to_receipts": [{"tool_event_digest": digest_a, "receipt_ids": ["RID_Z"]}],
}
index_path.write_text(json.dumps(index_bad_shape, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
if get_tool_events_for_receipt(root, "RID_Z"):
    raise SystemExit("FAIL:BAD_SHAPE_SHOULD_BE_EMPTY")
if get_receipts_for_tool_event(root, digest_a):
    raise SystemExit("FAIL:BAD_SHAPE_REVERSE_SHOULD_BE_EMPTY")

summary["bad_shape_empty"] = True
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$RESULT_DIR/run1.json"
R2="$RESULT_DIR/run2.json"
run_once "$R1"
run_once "$R2"

_HASHES="$(tool_event_receipt_replay_require_deterministic_files "$R1" "$R2" "FAIL:NON_DETERMINISTIC")"
H1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
H2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"

echo "TOOL_EVENT_RECEIPT_NEGATIVE_MATRIX=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
