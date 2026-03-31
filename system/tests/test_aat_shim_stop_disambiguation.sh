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

normalize_markers() {
  sed -E -e 's/[[:space:]]+$//'
}

parse_kv() {
  local line="$1"
  local key="$2"
  printf '%s\n' "$line" | tr ' ' '\n' | rg "^${key}=" | head -n1 | cut -d= -f2-
}

run_one() {
  local strict="$1"
  local bundle="$2"
  local outcome_file="$3"
  local out rc marker_count marker

  set +e
  out="$(bash "$ROOT/scripts/run_validate_proof_bundle_with_aat_shim.sh" --bundle-dir "$bundle" --strict "$strict" --outcome-file "$outcome_file" 2>&1)"
  rc=$?
  set -e

  marker_count="$(printf '%s\n' "$out" | rg -c '^AAT_SHIM_OUTCOME ')"
  [[ "$marker_count" -eq 1 ]] || {
    echo "FAIL: expected exactly one outcome marker (strict=$strict) got $marker_count"
    return 1
  }
  marker="$(printf '%s\n' "$out" | rg '^AAT_SHIM_OUTCOME ' | head -n1)"

  [[ "$(parse_kv "$marker" "strict")" == "$strict" ]] || { echo "FAIL: strict mismatch"; return 1; }
  [[ "$(parse_kv "$marker" "rc")" == "$rc" ]] || { echo "FAIL: rc mismatch"; return 1; }
  [[ "$(parse_kv "$marker" "shim_status")" == "STOP" ]] || { echo "FAIL: shim_status expected STOP"; return 1; }

  stage="$(parse_kv "$marker" "stop_stage")"
  code="$(parse_kv "$marker" "stop_code")"
  case "$stage" in
    PRE_SHIM|SHIM|POST_SHIM|UNKNOWN) ;;
    *) echo "FAIL: invalid stop_stage=$stage"; return 1 ;;
  esac

  if [[ "$code" != "NONE" && "$code" != "UNKNOWN" ]]; then
    [[ "$code" =~ ^RC-[A-Z0-9_-]+$ || "$code" =~ ^AAT_[A-Z0-9_-]+$ || "$code" =~ ^STOP:[A-Z0-9_-]+$ ]] || {
      echo "FAIL: invalid stop_code=$code"
      return 1
    }
  fi

  [[ -f "$outcome_file" ]] || { echo "FAIL: missing outcome_file"; return 1; }
  rg -n '^strict='"$strict"'$' "$outcome_file" >/dev/null
  rg -n '^rc='"$rc"'$' "$outcome_file" >/dev/null
  rg -n '^shim_status=STOP$' "$outcome_file" >/dev/null
  rg -n '^stop_stage=(PRE_SHIM|SHIM|POST_SHIM|UNKNOWN)$' "$outcome_file" >/dev/null
  rg -n '^stop_code=(NONE|UNKNOWN|RC-[A-Z0-9_-]+|AAT_[A-Z0-9_-]+|STOP:[A-Z0-9_-]+)$' "$outcome_file" >/dev/null

  printf '%s\n' "$marker"
}

select_real_bundle() {
  local list_file="$1"
  find "$ROOT/out/proof-bundles" -maxdepth 2 -type f -name 'proof_packet.tar' 2>/dev/null | sort > "$list_file"
  head -n1 "$list_file" | xargs -I{} dirname "{}"
}

run_once() {
  local tmp bundle marker0 marker1
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/aat-shim-stop-disambig.XXXXXX")"
  trap 'rm -rf "$tmp"' RETURN

  [[ -d "$HARD_STOP_AAT_DIR" ]] || { echo "FAIL: missing HARD_STOP_AAT_DIR=$HARD_STOP_AAT_DIR"; return 1; }

  bundle=""
  if [[ -d "$ROOT/out/proof-bundles" ]]; then
    bundle="$(select_real_bundle "$tmp/real_bundle_candidates.txt")"
  fi
  if [[ -z "$bundle" || ! -d "$bundle" ]]; then
    bundle="$tmp/synth_bundle"
    make_valid_bundle "$bundle"
  fi

  if ! python3 "$ROOT/scripts/aat_stage_into_proof_bundle.py" --bundle-dir "$bundle" --aat-dir "$HARD_STOP_AAT_DIR" >/dev/null 2>&1; then
    echo "FAIL: unable to stage hard-stop AAT inputs"
    return 1
  fi

  marker0="$(run_one 0 "$bundle" "$tmp/outcome.strict0.txt")"
  marker1="$(run_one 1 "$bundle" "$tmp/outcome.strict1.txt")"
  printf '%s\n' "$marker0"
  printf '%s\n' "$marker1"
  echo "CASE=STOP_DISAMBIGUATION PASS"
}

main() {
  local r1 r2 h1 h2
  r1="$(mktemp)"
  r2="$(mktemp)"

  run_once | normalize_markers > "$r1"
  run_once | normalize_markers > "$r2"

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
