#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

run_once() {
  local run_id="$1"
  local out_base="$ROOT/out/test-release-gate-input-manifest"
  local bundle_dir="$out_base/$run_id"

  rm -rf "$bundle_dir"

  # Task 0 audit adjustment: PASS if both token fragments exist.
  if rg -q 'AAT_STAGE_BLOCKED=' "$ROOT/scripts/aat_stage_into_proof_bundle.py" \
    && rg -q 'AAT_STAGE_NO_TOOL_EVENTS' "$ROOT/scripts/aat_stage_into_proof_bundle.py"; then
    echo "E_STAGE_BLOCK_TOKEN_AUDIT=PASS"
  else
    echo "FAIL:E_STAGE_BLOCK_TOKEN_AUDIT"
    return 1
  fi

  set +e
  env \
    GOV_PROFILE=dev \
    RELEASE_GATE_RUN_ID="$run_id" \
    RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$out_base" \
    bash "$ROOT/system/scripts/release-gate.sh" >/dev/null 2>&1
  local rc=$?
  set -e
  [[ "$rc" -eq 0 ]] || { echo "FAIL:RELEASE_GATE_RC=$rc"; return 1; }

  [[ -f "$bundle_dir/input_manifest.json" ]] || { echo "FAIL:INPUT_MANIFEST_MISSING"; return 1; }

  local parsed
  parsed="$(python3 - <<'PY' "$bundle_dir/input_manifest.json"
import hashlib, json, sys
from pathlib import Path

p = Path(sys.argv[1])
doc = json.loads(p.read_text(encoding='utf-8'))
if not isinstance(doc, dict):
    raise SystemExit('FAIL:NOT_OBJECT')
if 'input_manifest_version' not in doc or 'inputs' not in doc:
    raise SystemExit('FAIL:MISSING_KEYS')
if not isinstance(doc['inputs'], list):
    raise SystemExit('FAIL:INPUTS_NOT_LIST')
for item in doc['inputs']:
    if not isinstance(item, dict):
        raise SystemExit('FAIL:ENTRY_NOT_OBJECT')
    if item.get('ref_type') != 'tool_event':
        raise SystemExit('FAIL:ENTRY_REF_TYPE')
    digest = item.get('digest')
    if not isinstance(digest, str) or digest == '':
        raise SystemExit('FAIL:ENTRY_DIGEST')
norm = json.dumps(doc, sort_keys=True, separators=(',', ':')) + '\n'
print('COUNT=' + str(len(doc['inputs'])))
print('SHA256=' + hashlib.sha256(norm.encode('utf-8')).hexdigest())
PY
)"

  local count hash
  count="$(printf '%s\n' "$parsed" | rg '^COUNT=' | cut -d= -f2)"
  hash="$(printf '%s\n' "$parsed" | rg '^SHA256=' | cut -d= -f2)"

  echo "CASE=INPUT_MANIFEST_EXISTS PASS"
  echo "CASE=INPUT_MANIFEST_SCHEMA PASS"
  echo "TOOL_EVENT_COUNT=$count"
  echo "INPUT_MANIFEST_SHA256=$hash"
}

main() {
  local r1 r2 h1 h2
  r1="$(mktemp)"
  r2="$(mktemp)"

  run_once "test_rg_input_manifest_run1" > "$r1"
  run_once "test_rg_input_manifest_run2" > "$r2"

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
