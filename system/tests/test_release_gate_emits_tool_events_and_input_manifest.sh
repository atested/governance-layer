#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_BASE="$ROOT/out/test-release-gate-tool-events"

bundle_name_for_run() {
  local run_id="$1"
  echo "$run_id"
}

validate_bundle() {
  local bundle_dir="$1"
  [[ -f "$bundle_dir/tool_events.jsonl" ]] || { echo "FAIL:TOOL_EVENTS_MISSING"; return 1; }
  [[ -f "$bundle_dir/input_manifest.json" ]] || { echo "FAIL:INPUT_MANIFEST_MISSING"; return 1; }

  local line_count
  line_count="$(wc -l < "$bundle_dir/tool_events.jsonl" | tr -d ' ')"
  [[ "$line_count" -ge 1 ]] || { echo "FAIL:TOOL_EVENTS_EMPTY"; return 1; }

  python3 - <<'PY' "$bundle_dir/tool_events.jsonl" "$bundle_dir/input_manifest.json"
import json
import sys
from pathlib import Path

ev_path = Path(sys.argv[1])
im_path = Path(sys.argv[2])
required = {"tool_event_version", "tool", "argv_norm", "rc", "stdout_sha256", "stderr_sha256"}

for raw in ev_path.read_text(encoding="utf-8").splitlines():
    if not raw.strip():
        raise SystemExit("FAIL:TOOL_EVENT_BLANK_LINE")
    obj = json.loads(raw)
    missing = sorted(required - set(obj.keys()))
    if missing:
        raise SystemExit("FAIL:TOOL_EVENT_KEYS")
    if obj.get("tool_event_version") != "v0":
        raise SystemExit("FAIL:TOOL_EVENT_VERSION")
    if not isinstance(obj.get("tool"), str) or not obj.get("tool"):
        raise SystemExit("FAIL:TOOL_EVENT_TOOL")
    if not isinstance(obj.get("argv_norm"), str):
        raise SystemExit("FAIL:TOOL_EVENT_ARGV_NORM")
    if not isinstance(obj.get("rc"), int):
        raise SystemExit("FAIL:TOOL_EVENT_RC")
    for k in ("stdout_sha256", "stderr_sha256"):
        v = obj.get(k)
        if not isinstance(v, str) or not v.startswith("sha256:"):
            raise SystemExit("FAIL:TOOL_EVENT_HASH")

im = json.loads(im_path.read_text(encoding="utf-8"))
if "input_manifest_version" not in im or "inputs" not in im:
    raise SystemExit("FAIL:INPUT_MANIFEST_KEYS")
if not isinstance(im["inputs"], list):
    raise SystemExit("FAIL:INPUT_MANIFEST_INPUTS_TYPE")
if len(im["inputs"]) < 1:
    raise SystemExit("FAIL:INPUT_MANIFEST_INPUTS_EMPTY")
for e in im["inputs"]:
    if not isinstance(e, dict):
        raise SystemExit("FAIL:INPUT_MANIFEST_ENTRY_TYPE")
    if e.get("ref_type") != "tool_event":
        raise SystemExit("FAIL:INPUT_MANIFEST_REF_TYPE")
    d = e.get("digest")
    if not isinstance(d, str) or not d:
        raise SystemExit("FAIL:INPUT_MANIFEST_DIGEST")
PY
}

manifest_hash() {
  python3 - <<'PY' "$1"
import hashlib, json, sys
from pathlib import Path
p = Path(sys.argv[1])
doc = json.loads(p.read_text(encoding='utf-8'))
norm = json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n"
print(hashlib.sha256(norm.encode('utf-8')).hexdigest())
PY
}

run_one() {
  local run_id="$1"
  local bundle_name
  bundle_name="$(bundle_name_for_run "$run_id")"
  rm -rf "$OUT_BASE/$bundle_name"

  set +e
  env GOV_PROFILE=dev RELEASE_GATE_SKIP_BASE=1 RELEASE_GATE_RUN_ID="$run_id" RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$OUT_BASE" \
    bash "$ROOT/system/scripts/release-gate.sh" >/dev/null 2>&1
  local rc=$?
  set -e
  [[ "$rc" -eq 0 ]] || { echo "FAIL:RELEASE_GATE_RC=$rc"; return 1; }

  local bundle_dir="$OUT_BASE/$bundle_name"
  validate_bundle "$bundle_dir"

  local ev_hash im_hash
  ev_hash="$(shasum -a 256 "$bundle_dir/tool_events.jsonl" | awk '{print $1}')"
  im_hash="$(manifest_hash "$bundle_dir/input_manifest.json")"

  echo "TOOL_EVENTS_SHA256=$ev_hash"
  echo "INPUT_MANIFEST_SHA256=$im_hash"
}

main() {
  mkdir -p "$OUT_BASE"
  local r1 r2 h1 h2
  r1="$(mktemp)"
  r2="$(mktemp)"

  run_one "test_rg_tool_events_run1" > "$r1"
  run_one "test_rg_tool_events_run2" > "$r2"

  h1="$(shasum -a 256 "$r1" | awk '{print $1}')"
  h2="$(shasum -a 256 "$r2" | awk '{print $1}')"

  cat "$r1"
  echo "RUN1_SHA256=$h1"
  echo "RUN2_SHA256=$h2"
  [[ "$h1" == "$h2" ]] || { echo "DETERMINISTIC=NO"; rm -f "$r1" "$r2"; exit 1; }
  echo "DETERMINISTIC=YES"

  rm -f "$r1" "$r2"
}

main "$@"
