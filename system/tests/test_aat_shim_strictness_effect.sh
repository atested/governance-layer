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
    -e 's|/tmp/aat-shim-strictness\.[A-Za-z0-9._-]+|<TMP_ROOT>|g' \
    -e 's|/var/folders/[^[:space:]]+/aat-shim-strictness\.[A-Za-z0-9._-]+|<TMP_ROOT>|g' \
    -e 's|'"$ROOT"'|<ROOT>|g'
}

run_case() {
  local strict="$1"
  local bundle="$2"
  local out rc
  set +e
  out="$(bash "$ROOT/scripts/run_validate_proof_bundle_with_aat_shim.sh" --bundle-dir "$bundle" --strict "$strict" 2>&1)"
  rc=$?
  set -e
  printf '%s\n' "$out"
  return "$rc"
}

run_once() {
  local tmp
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/aat-shim-strictness.XXXXXX")"
  trap 'rm -rf "$tmp"' RETURN

  [[ -d "$PASS_AAT_DIR" ]] || { echo "FAIL: missing PASS_AAT_DIR=$PASS_AAT_DIR"; return 1; }
  [[ -d "$NONAD_AAT_DIR" ]] || { echo "FAIL: missing NONAD_AAT_DIR=$NONAD_AAT_DIR"; return 1; }

  local pass_bundle="$tmp/pass_bundle"
  local nonad_bundle="$tmp/nonad_bundle"
  make_valid_bundle "$pass_bundle"
  make_valid_bundle "$nonad_bundle"

  python3 "$ROOT/scripts/aat_stage_into_proof_bundle.py" --bundle-dir "$pass_bundle" --aat-dir "$PASS_AAT_DIR" >/dev/null
  python3 "$ROOT/scripts/aat_stage_into_proof_bundle.py" --bundle-dir "$nonad_bundle" --aat-dir "$NONAD_AAT_DIR" >/dev/null

  local out_strict1_pass out_strict0_nonad out_strict1_nonad
  local rc_strict1_pass rc_strict0_nonad rc_strict1_nonad

  set +e
  out_strict1_pass="$(run_case 1 "$pass_bundle")"
  rc_strict1_pass=$?
  out_strict0_nonad="$(run_case 0 "$nonad_bundle")"
  rc_strict0_nonad=$?
  out_strict1_nonad="$(run_case 1 "$nonad_bundle")"
  rc_strict1_nonad=$?
  set -e

  [[ "$rc_strict1_pass" -eq 0 ]] || { echo "FAIL: strict=1 pass expected rc=0 got $rc_strict1_pass"; printf '%s\n' "$out_strict1_pass"; return 1; }
  printf '%s\n' "$out_strict1_pass" | rg -n '^AAT_SHIM_RESULT=PASS REASON_CODE=NONE LEDGER_APPENDED=YES$' >/dev/null

  [[ "$rc_strict0_nonad" -eq 0 ]] || { echo "FAIL: strict=0 nonad expected rc=0 got $rc_strict0_nonad"; printf '%s\n' "$out_strict0_nonad"; return 1; }
  [[ "$rc_strict1_nonad" -eq 1 ]] || { echo "FAIL: strict=1 nonad expected rc=1 got $rc_strict1_nonad"; printf '%s\n' "$out_strict1_nonad"; return 1; }

  printf '%s\n' "$out_strict0_nonad" | rg -n '^AAT_SHIM_RESULT=NON_ADMISSIBLE REASON_CODE=AAT_C1_CONTRADICTION LEDGER_APPENDED=YES$' >/dev/null
  printf '%s\n' "$out_strict1_nonad" | rg -n '^AAT_SHIM_RESULT=NON_ADMISSIBLE REASON_CODE=AAT_C1_CONTRADICTION LEDGER_APPENDED=YES$' >/dev/null

  local h0 h1
  h0="$(printf '%s\n' "$out_strict0_nonad" | shasum -a 256 | awk '{print $1}')"
  h1="$(printf '%s\n' "$out_strict1_nonad" | shasum -a 256 | awk '{print $1}')"

  if [[ "$rc_strict0_nonad" -eq "$rc_strict1_nonad" && "$h0" == "$h1" ]]; then
    echo "FAIL: strictness effect absent (rc and output identical)"
    return 1
  fi

  echo "STRICT_NONAD_RC_STRICT0=$rc_strict0_nonad"
  echo "STRICT_NONAD_RC_STRICT1=$rc_strict1_nonad"
  echo "STRICT_NONAD_OUT_SHA_STRICT0=$h0"
  echo "STRICT_NONAD_OUT_SHA_STRICT1=$h1"
  echo "CASE=STRICTNESS_EFFECT PASS"
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

  if [[ "$h1" != "$h2" ]]; then
    echo "DETERMINISTIC=NO"
    diff -u "$r1" "$r2" | sed -n '1,80p' || true
    rm -f "$r1" "$r2"
    exit 1
  fi

  echo "DETERMINISTIC=YES"
  rm -f "$r1" "$r2"
}

main "$@"
