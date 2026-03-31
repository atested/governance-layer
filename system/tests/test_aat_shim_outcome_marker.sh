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

normalize_markers() {
  sed -E \
    -e 's/[[:space:]]+$//' \
    -e 's|'"$ROOT"'|<ROOT>|g' \
    -e 's|/tmp/aat-shim-outcome\.[A-Za-z0-9._-]+|<TMP_ROOT>|g' \
    -e 's|/var/folders/[^[:space:]]+/aat-shim-outcome\.[A-Za-z0-9._-]+|<TMP_ROOT>|g'
}

parse_kv() {
  local line="$1"
  local key="$2"
  printf '%s\n' "$line" | tr ' ' '\n' | rg "^${key}=" | head -n1 | cut -d= -f2-
}

run_wrapper() {
  local strict="$1"
  local bundle="$2"
  local outcome_file="$3"
  local out rc marker_count marker_line

  set +e
  out="$(bash "$ROOT/scripts/run_validate_proof_bundle_with_aat_shim.sh" --bundle-dir "$bundle" --strict "$strict" --outcome-file "$outcome_file" 2>&1)"
  rc=$?
  set -e

  marker_count="$(printf '%s\n' "$out" | rg -c '^AAT_SHIM_OUTCOME ')"
  [[ "$marker_count" -eq 1 ]] || {
    echo "FAIL: expected exactly one AAT_SHIM_OUTCOME line, got $marker_count"
    printf '%s\n' "$out"
    return 1
  }
  marker_line="$(printf '%s\n' "$out" | rg '^AAT_SHIM_OUTCOME ' | head -n1)"

  local strict_kv rc_kv status_kv
  strict_kv="$(parse_kv "$marker_line" "strict")"
  rc_kv="$(parse_kv "$marker_line" "rc")"
  status_kv="$(parse_kv "$marker_line" "shim_status")"

  [[ "$strict_kv" == "$strict" ]] || { echo "FAIL: marker strict mismatch expected=$strict actual=$strict_kv"; return 1; }
  [[ "$rc_kv" == "$rc" ]] || { echo "FAIL: marker rc mismatch expected=$rc actual=$rc_kv"; return 1; }

  [[ -f "$outcome_file" ]] || { echo "FAIL: missing outcome_file=$outcome_file"; return 1; }
  rg -n "^strict=$strict$" "$outcome_file" >/dev/null
  rg -n "^rc=$rc$" "$outcome_file" >/dev/null
  rg -n "^shim_status=(ADMISSIBLE|NON_ADMISSIBLE|UNKNOWN|STOP)$" "$outcome_file" >/dev/null

  printf 'STRICT=%s RC=%s SHIM_STATUS=%s\n' "$strict" "$rc" "$status_kv"
  printf 'MARKER=%s\n' "$marker_line"
  return 0
}

run_once() {
  local tmp
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/aat-shim-outcome.XXXXXX")"
  trap 'rm -rf "$tmp"' RETURN

  [[ -d "$PASS_AAT_DIR" ]] || { echo "FAIL: missing PASS_AAT_DIR=$PASS_AAT_DIR"; return 1; }
  [[ -d "$NONAD_AAT_DIR" ]] || { echo "FAIL: missing NONAD_AAT_DIR=$NONAD_AAT_DIR"; return 1; }

  local pass_bundle="$tmp/pass_bundle"
  local nonad_bundle="$tmp/nonad_bundle"
  make_valid_bundle "$pass_bundle"
  make_valid_bundle "$nonad_bundle"

  python3 "$ROOT/scripts/aat_stage_into_proof_bundle.py" --bundle-dir "$pass_bundle" --aat-dir "$PASS_AAT_DIR" >/dev/null
  python3 "$ROOT/scripts/aat_stage_into_proof_bundle.py" --bundle-dir "$nonad_bundle" --aat-dir "$NONAD_AAT_DIR" >/dev/null

  run_wrapper 0 "$nonad_bundle" "$tmp/outcome.strict0.txt" >"$tmp/run.strict0.txt"
  run_wrapper 1 "$nonad_bundle" "$tmp/outcome.strict1.txt" >"$tmp/run.strict1.txt"

  local rc0 rc1 status0 status1
  rc0="$(rg -n '^STRICT=0 RC=' "$tmp/run.strict0.txt" | sed -E 's/^.*RC=([0-9]+).*$/\1/')"
  rc1="$(rg -n '^STRICT=1 RC=' "$tmp/run.strict1.txt" | sed -E 's/^.*RC=([0-9]+).*$/\1/')"
  status0="$(rg -n '^STRICT=0 RC=' "$tmp/run.strict0.txt" | sed -E 's/^.*SHIM_STATUS=([A-Z_]+).*$/\1/')"
  status1="$(rg -n '^STRICT=1 RC=' "$tmp/run.strict1.txt" | sed -E 's/^.*SHIM_STATUS=([A-Z_]+).*$/\1/')"

  [[ "$rc0" == "0" ]] || { echo "FAIL: expected strict=0 rc=0 got $rc0"; return 1; }
  [[ "$rc1" == "1" ]] || { echo "FAIL: expected strict=1 rc=1 got $rc1"; return 1; }

  [[ "$status0" == "NON_ADMISSIBLE" || "$status0" == "UNKNOWN" ]] || { echo "FAIL: unexpected strict=0 status=$status0"; return 1; }
  [[ "$status1" == "NON_ADMISSIBLE" || "$status1" == "UNKNOWN" ]] || { echo "FAIL: unexpected strict=1 status=$status1"; return 1; }

  if [[ "$status0" == "NON_ADMISSIBLE" || "$status1" == "NON_ADMISSIBLE" ]]; then
    [[ "$status0" == "NON_ADMISSIBLE" && "$status1" == "NON_ADMISSIBLE" ]] || {
      echo "FAIL: inconsistent status extraction (one NON_ADMISSIBLE, one UNKNOWN)"
      return 1
    }
  else
    [[ "$status0" == "UNKNOWN" && "$status1" == "UNKNOWN" ]] || {
      echo "FAIL: inconsistent UNKNOWN fallback"
      return 1
    }
  fi

  cat "$tmp/run.strict0.txt"
  cat "$tmp/run.strict1.txt"
  echo "CASE=OUTCOME_MARKER PASS"
}

main() {
  local r1 r2 h1 h2
  r1="$(mktemp)"
  r2="$(mktemp)"

  run_once | normalize_markers >"$r1"
  run_once | normalize_markers >"$r2"

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
