#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS_AAT_DIR="$ROOT/system/tests/fixtures/proof_bundle_with_aat_inputs/pass_aat_preferred/aat"
NONAD_AAT_DIR="$ROOT/system/tests/fixtures/proof_bundle_with_aat_inputs/non_admissible_aat_preferred/aat"

make_valid_bundle() {
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

normalize() {
  sed -E \
    -e 's|/tmp/aat-shim-operator-pilot\.[A-Za-z0-9._-]+|<TMP_ROOT>|g' \
    -e 's|/var/folders/[^[:space:]]+/aat-shim-operator-pilot\.[A-Za-z0-9._-]+|<TMP_ROOT>|g'
}

run_once() {
  local tmp
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/aat-shim-operator-pilot.XXXXXX")"
  trap 'rm -rf "$tmp"' RETURN

  [[ -d "$PASS_AAT_DIR" ]] || { echo "FAIL: missing PASS_AAT_DIR=$PASS_AAT_DIR"; return 1; }
  [[ -d "$NONAD_AAT_DIR" ]] || { echo "FAIL: missing NONAD_AAT_DIR=$NONAD_AAT_DIR"; return 1; }

  local pass_bundle="$tmp/pass_bundle"
  local nonad_bundle="$tmp/nonad_bundle"
  make_valid_bundle "$pass_bundle"
  make_valid_bundle "$nonad_bundle"

  local stage_pass_out="$tmp/stage_pass.out"
  local stage_nonad_out="$tmp/stage_nonad.out"

  python3 "$ROOT/scripts/aat_stage_into_proof_bundle.py" --bundle-dir "$pass_bundle" --aat-dir "$PASS_AAT_DIR" >"$stage_pass_out"
  python3 "$ROOT/scripts/aat_stage_into_proof_bundle.py" --bundle-dir "$nonad_bundle" --aat-dir "$NONAD_AAT_DIR" >"$stage_nonad_out"

  rg -n '^AAT_STAGE=PASS$' "$stage_pass_out" >/dev/null
  rg -n '^AAT_STAGE=PASS$' "$stage_nonad_out" >/dev/null
  rg -n '^COPIED_FILES=11$' "$stage_pass_out" >/dev/null
  rg -n '^DEST=aat/$' "$stage_pass_out" >/dev/null

  local out
  local rc

  set +e
  out="$(bash "$ROOT/scripts/run_validate_proof_bundle_with_aat_shim.sh" --bundle-dir "$pass_bundle" --strict 1 2>&1)"
  rc=$?
  set -e
  [[ "$rc" -eq 0 ]] || { echo "FAIL: strict1 pass expected rc=0 got $rc"; printf '%s\n' "$out"; return 1; }
  printf '%s\n' "$out" | rg -n '^AAT_SHIM_OUTCOME strict=1 rc=0 shim_status=ADMISSIBLE stop_stage=UNKNOWN stop_code=NONE$' >/dev/null

  set +e
  out="$(bash "$ROOT/scripts/run_validate_proof_bundle_with_aat_shim.sh" --bundle-dir "$nonad_bundle" --strict 1 2>&1)"
  rc=$?
  set -e
  [[ "$rc" -eq 1 ]] || { echo "FAIL: strict1 nonad expected rc=1 got $rc"; printf '%s\n' "$out"; return 1; }
  printf '%s\n' "$out" | rg -n '^AAT_SHIM_OUTCOME strict=1 rc=1 shim_status=NON_ADMISSIBLE stop_stage=UNKNOWN stop_code=NONE$' >/dev/null

  set +e
  out="$(bash "$ROOT/scripts/run_validate_proof_bundle_with_aat_shim.sh" --bundle-dir "$nonad_bundle" --strict 0 2>&1)"
  rc=$?
  set -e
  [[ "$rc" -eq 0 ]] || { echo "FAIL: strict0 nonad expected rc=0 got $rc"; printf '%s\n' "$out"; return 1; }
  printf '%s\n' "$out" | rg -n '^AAT_SHIM_OUTCOME strict=0 rc=0 shim_status=NON_ADMISSIBLE stop_stage=UNKNOWN stop_code=NONE$' >/dev/null

  echo "CASE=strict1_pass PASS"
  echo "CASE=strict1_nonad PASS"
  echo "CASE=strict0_nonad_advisory PASS"
}

main() {
  local r1 r2 h1 h2
  r1="$(mktemp)"
  r2="$(mktemp)"

  run_once | normalize >"$r1"
  run_once | normalize >"$r2"

  h1="$(shasum -a 256 "$r1" | awk '{print $1}')"
  h2="$(shasum -a 256 "$r2" | awk '{print $1}')"

  cat "$r1"
  echo "RUN1_SHA256=$h1"
  echo "RUN2_SHA256=$h2"

  [[ "$h1" == "$h2" ]] || {
    echo "DETERMINISTIC=NO"
    diff -u "$r1" "$r2" | sed -n '1,80p' || true
    rm -f "$r1" "$r2"
    exit 1
  }
  echo "DETERMINISTIC=YES"
  rm -f "$r1" "$r2"
}

main "$@"
