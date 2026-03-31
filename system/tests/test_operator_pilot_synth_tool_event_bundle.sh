#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AAT_DIR="$ROOT/system/tests/fixtures/proof_bundle_with_aat_inputs/pass_aat_preferred/aat"

make_bundle() {
  local dir="$1"
  mkdir -p "$dir"
  python3 - <<'PY' "$dir"
import io, json, tarfile, sys, pathlib, hashlib
out = pathlib.Path(sys.argv[1])
(out/'versions.txt').write_text('repo_git_sha=deadbeef\npython_version=3.x\n', encoding='utf-8')
(out/'release_gate_log.txt').write_text('result=PASS\nprofile=ci\n', encoding='utf-8')
(out/'proof_packet_verify_summary.json').write_text(json.dumps({'report_version':'proof_packet_verify_summary_v1','result':'PASS'}, sort_keys=True, separators=(',',':'))+'\n', encoding='utf-8')
(out/'input_manifest.json').write_text(json.dumps({'input_manifest_version':'v0','inputs':[{'ref_type':'tool_event','digest':'sha256:1111111111111111111111111111111111111111111111111111111111111111'}]}, sort_keys=True, separators=(',',':'))+'\n', encoding='utf-8')
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
  [[ -d "$AAT_DIR" ]] || { echo 'FAIL:AAT_DIR_MISSING'; return 1; }

  local tmp bundle out_stage rc_stage out0 out1 rc0 rc1 marker0 marker1 c0 c1
  tmp="$(mktemp -d "$ROOT/out/operator-pilot-synth.XXXXXX")"
  trap 'rm -rf "$tmp"' RETURN

  bundle="$tmp/bundle"
  make_bundle "$bundle"

  set +e
  out_stage="$(python3 "$ROOT/scripts/aat_stage_into_proof_bundle.py" --bundle-dir "$bundle" --aat-dir "$AAT_DIR" 2>/dev/null)"
  rc_stage=$?
  set -e
  [[ "$rc_stage" -eq 0 ]] || { echo "FAIL:STAGE_RC=$rc_stage"; return 1; }
  printf '%s\n' "$out_stage" | rg -n '^AAT_STAGE_BLOCKED=' >/dev/null && { echo 'FAIL:STAGE_BLOCKED_UNEXPECTED'; return 1; }

  set +e
  out0="$(bash "$ROOT/scripts/run_validate_proof_bundle_with_aat_shim.sh" --bundle-dir "$bundle" --strict 0 2>&1)"
  rc0=$?
  out1="$(bash "$ROOT/scripts/run_validate_proof_bundle_with_aat_shim.sh" --bundle-dir "$bundle" --strict 1 2>&1)"
  rc1=$?
  set -e

  c0="$(printf '%s\n' "$out0" | rg -c '^AAT_SHIM_OUTCOME ')"
  c1="$(printf '%s\n' "$out1" | rg -c '^AAT_SHIM_OUTCOME ')"
  [[ "$c0" -eq 1 ]] || { echo 'FAIL:STRICT0_MARKER_COUNT'; return 1; }
  [[ "$c1" -eq 1 ]] || { echo 'FAIL:STRICT1_MARKER_COUNT'; return 1; }

  marker0="$(printf '%s\n' "$out0" | rg '^AAT_SHIM_OUTCOME ' | head -n1)"
  marker1="$(printf '%s\n' "$out1" | rg '^AAT_SHIM_OUTCOME ' | head -n1)"

  printf '%s\n%s\n' "$marker0" "$marker1" | rg -n 'stop_code=AAT_K1_PHANTOM_ACTION' >/dev/null && { echo 'FAIL:K1_PHANTOM_PRESENT'; return 1; }

  echo 'CASE=STAGE_NOT_BLOCKED PASS'
  echo 'CASE=OUTCOME_MARKERS_PRESENT PASS'
  echo 'CASE=NO_K1_PHANTOM PASS'
  echo "$marker0"
  echo "$marker1"
  echo "RC0=$rc0"
  echo "RC1=$rc1"

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
  [[ "$h1" == "$h2" ]] || { echo 'DETERMINISTIC=NO'; exit 1; }
  echo 'DETERMINISTIC=YES'
  rm -f "$r1" "$r2"
}

main "$@"
