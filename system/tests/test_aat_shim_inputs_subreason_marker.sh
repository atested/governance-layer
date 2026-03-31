#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HARD_STOP_AAT_DIR="$ROOT/system/tests/fixtures/aat_gate_c/hard_stop"

make_valid_bundle() {
  local dir="$1"
  mkdir -p "$dir"
  python3 - <<'PY' "$dir"
import io, json, tarfile, sys, pathlib, hashlib
out = pathlib.Path(sys.argv[1])
(out/'versions.txt').write_text('repo_git_sha=deadbeef\npython_version=3.x\n', encoding='utf-8')
(out/'release_gate_log.txt').write_text('result=PASS\nprofile=ci\n', encoding='utf-8')
(out/'proof_packet_verify_summary.json').write_text(json.dumps({'report_version':'proof_packet_verify_summary_v1','result':'PASS'}, sort_keys=True, separators=(',',':'))+'\n', encoding='utf-8')
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
  local tmp bundle wrapper_out raw_out marker sub_count sub_line
  tmp="$(mktemp -d "$ROOT/out/aat-shim-inputs-subreason.XXXXXX")"
  bundle="$tmp/bundle"
  make_valid_bundle "$bundle"

  [[ -d "$HARD_STOP_AAT_DIR" ]] || { echo "FAIL:missing_hard_stop_fixture"; rm -rf "$tmp"; exit 1; }
  python3 "$ROOT/scripts/aat_stage_into_proof_bundle.py" --bundle-dir "$bundle" --aat-dir "$HARD_STOP_AAT_DIR" >/dev/null

  wrapper_out="$(bash "$ROOT/scripts/run_validate_proof_bundle_with_aat_shim.sh" --bundle-dir "$bundle" --strict 0 2>/dev/null || true)"
  marker="$(printf '%s\n' "$wrapper_out" | rg '^AAT_SHIM_OUTCOME ' | head -n1 || true)"
  [[ -n "$marker" ]] || { echo "FAIL:missing_outcome_marker"; rm -rf "$tmp"; exit 1; }
  printf '%s\n' "$marker" | rg -q 'stop_code=AAT_SHIM_INPUTS'

  raw_out="$(AAT_SHIM_ENABLE=1 AAT_SHIM_STRICT=0 bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$bundle" 2>/dev/null || true)"
  sub_count="$(printf '%s\n' "$raw_out" | rg -c '^AAT_INPUTS_SUBREASON=AAT_INPUTS_[A-Z0-9_]+$')"
  [[ "$sub_count" -eq 1 ]] || { echo "FAIL:subreason_count=$sub_count"; rm -rf "$tmp"; exit 1; }
  sub_line="$(printf '%s\n' "$raw_out" | rg '^AAT_INPUTS_SUBREASON=AAT_INPUTS_[A-Z0-9_]+$' | head -n1)"

  token="${sub_line#AAT_INPUTS_SUBREASON=}"
  case "$token" in
    AAT_INPUTS_MISSING_FILE|AAT_INPUTS_LAYOUT_AMBIGUOUS|AAT_INPUTS_JSON_INVALID|AAT_INPUTS_SCHEMA_INVALID|AAT_INPUTS_BINDING_MISMATCH|AAT_INPUTS_UNKNOWN) ;;
    *) echo "FAIL:token_not_whitelisted"; rm -rf "$tmp"; exit 1 ;;
  esac

  printf '%s\n' "$sub_line"
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
  [[ "$h1" == "$h2" ]] || { echo "DETERMINISTIC=NO"; diff -u "$r1" "$r2" | sed -n '1,80p' || true; rm -f "$r1" "$r2"; exit 1; }
  echo "DETERMINISTIC=YES"
  rm -f "$r1" "$r2"
}

main "$@"
