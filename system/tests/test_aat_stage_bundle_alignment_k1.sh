#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HARD_STOP_AAT_DIR="$ROOT/system/tests/fixtures/aat_gate_c/hard_stop"
PASS_AAT_DIR="$ROOT/system/tests/fixtures/proof_bundle_with_aat_inputs/pass_aat_preferred/aat"

make_bundle() {
  local dir="$1"
  local with_tool_event="$2"
  mkdir -p "$dir"
  python3 - <<'PY' "$dir" "$with_tool_event"
import io, json, tarfile, sys, pathlib, hashlib
out = pathlib.Path(sys.argv[1])
with_tool_event = sys.argv[2] == "yes"
(out/'versions.txt').write_text('repo_git_sha=deadbeef\npython_version=3.x\n', encoding='utf-8')
(out/'release_gate_log.txt').write_text('result=PASS\nprofile=ci\n', encoding='utf-8')
(out/'proof_packet_verify_summary.json').write_text(json.dumps({'report_version':'proof_packet_verify_summary_v1','result':'PASS'}, sort_keys=True, separators=(',',':'))+'\n', encoding='utf-8')
inputs = []
if with_tool_event:
    inputs.append({'ref_type':'tool_event','digest':'sha256:1111111111111111111111111111111111111111111111111111111111111111'})
(out/'input_manifest.json').write_text(json.dumps({'input_manifest_version':'v0','inputs':inputs}, sort_keys=True, separators=(',',':'))+'\n', encoding='utf-8')
manifest = {'proof_packet_version':'proof_packet_v1','files':{'record.json':{'sha256':'dummy','size_bytes':2}}}
tar_path = out/'proof_packet.tar'
with tarfile.open(tar_path, 'w') as tf:
    payload = json.dumps(manifest, sort_keys=True, separators=(',',':')).encode()+b'\n'
    ti = tarfile.TarInfo('manifest.json'); ti.size=len(payload); ti.mtime=0; ti.uid=0; ti.gid=0; ti.uname=''; ti.gname=''; ti.mode=0o644
    tf.addfile(ti, io.BytesIO(payload))
    rec = b'{}'
    ti = tarfile.TarInfo('payload/record.json'); ti.size=len(rec); ti.mtime=0; ti.uid=0; ti.gid=0; ti.uname=''; ti.gname=''; ti.mode=0o644
    tf.addfile(ti, io.BytesIO(rec))
h = hashlib.sha256(tar_path.read_bytes()).hexdigest()
(out/'proof_packet.sha256').write_text(f'{h}  proof_packet.tar\n', encoding='utf-8')
PY
}

run_once() {
  local tmp b0 b1 out0 out1 rc0 rc1 shim_out shim_rc
  tmp="$(mktemp -d "$ROOT/out/aat-stage-k1.XXXXXX")"
  trap 'rm -rf "$tmp"' RETURN

  b0="$tmp/no_tool_events"
  b1="$tmp/has_tool_events"
  make_bundle "$b0" "no"
  make_bundle "$b1" "yes"

  set +e
  out0="$(python3 "$ROOT/scripts/aat_stage_into_proof_bundle.py" --bundle-dir "$b0" --aat-dir "$PASS_AAT_DIR" 2>/dev/null)"
  rc0=$?
  set -e
  [[ "$rc0" -ne 0 ]] || { echo "FAIL:no_tool_events should block"; return 1; }
  [[ "$(printf '%s\n' "$out0" | wc -l | tr -d ' ')" -eq 1 ]] || { echo "FAIL:no_tool_events should emit one line"; return 1; }
  printf '%s\n' "$out0" | rg -n '^AAT_STAGE_BLOCKED=AAT_STAGE_NO_TOOL_EVENTS$' >/dev/null

  set +e
  out1="$(python3 "$ROOT/scripts/aat_stage_into_proof_bundle.py" --bundle-dir "$b1" --aat-dir "$HARD_STOP_AAT_DIR" 2>/dev/null)"
  rc1=$?
  set -e
  [[ "$rc1" -eq 0 ]] || { echo "FAIL:has_tool_events hard_stop staging should pass"; return 1; }
  printf '%s\n' "$out1" | rg -n '^AAT_STAGE_BLOCKED=' >/dev/null && { echo "FAIL:unexpected blocked marker"; return 1; }
  python3 - <<'PY' "$b1/aat/claims_evidence_map.json"
import json,sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
claims = doc.get("claims", [])
if claims:
    raise SystemExit(1)
PY
  python3 - <<'PY' "$b1/aat/input_manifest.json"
import json,sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
inputs = doc.get("inputs", [])
tool = [x for x in inputs if isinstance(x, dict) and x.get("ref_type") == "tool_event" and isinstance(x.get("digest"), str)]
if not tool:
    raise SystemExit(1)
PY

  local b2 pass_stage_out pass_stage_rc
  b2="$tmp/has_tool_events_pass_fixture"
  make_bundle "$b2" "yes"
  set +e
  pass_stage_out="$(python3 "$ROOT/scripts/aat_stage_into_proof_bundle.py" --bundle-dir "$b2" --aat-dir "$PASS_AAT_DIR" 2>/dev/null)"
  pass_stage_rc=$?
  set -e
  [[ "$pass_stage_rc" -eq 0 ]] || { echo "FAIL:has_tool_events pass staging should pass"; return 1; }
  printf '%s\n' "$pass_stage_out" | rg -n '^AAT_STAGE_BLOCKED=' >/dev/null && { echo "FAIL:unexpected blocked marker for pass fixture"; return 1; }

  set +e
  shim_out="$(bash "$ROOT/scripts/run_validate_proof_bundle_with_aat_shim.sh" --bundle-dir "$b2" --strict 0 2>&1)"
  shim_rc=$?
  set -e
  [[ "$shim_rc" -eq 0 ]] || { echo "FAIL:expected strict0 pass fixture to return rc=0"; return 1; }
  printf '%s\n' "$shim_out" | rg -n '^AAT_SHIM_OUTCOME ' >/dev/null
  printf '%s\n' "$shim_out" | rg -n 'stop_code=AAT_K1_PHANTOM_ACTION' >/dev/null && { echo "FAIL:K1 phantom still present"; return 1; }

  echo "CASE=NO_TOOL_EVENTS_BLOCK PASS"
  echo "CASE=HAS_TOOL_EVENTS_STAGE_ALIGNED PASS"
  echo "CASE=HAS_TOOL_EVENTS_NO_K1 PASS"
  trap - RETURN
  rm -rf "$tmp"
}

main() {
  local r1 r2 h1 h2
  r1="$(mktemp)"
  r2="$(mktemp)"
  run_once >"$r1"
  run_once >"$r2"
  h1="$(shasum -a 256 "$r1" | awk '{print $1}')"
  h2="$(shasum -a 256 "$r2" | awk '{print $1}')"
  cat "$r1"
  echo "RUN1_SHA256=$h1"
  echo "RUN2_SHA256=$h2"
  [[ "$h1" == "$h2" ]] || { echo "DETERMINISTIC=NO"; exit 1; }
  echo "DETERMINISTIC=YES"
  rm -f "$r1" "$r2"
}

main "$@"
