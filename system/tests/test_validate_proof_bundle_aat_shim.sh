#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
TMP_ROOT="${TMPDIR:-/tmp}"
TMP_ROOT="${TMP_ROOT%/}"
USING_TEMP_LOG_DIR=0
CLEANUP_FILES=()

LOG_DIR=""
LOG_STDOUT=""
LOG_STDERR=""
LAST_CAPTURE_STDOUT=""
LAST_CAPTURE_STDERR=""
MODE_SINGLE_RUN=0

init_log_dir() {
  local preferred_dir=""
  local tmp_dir=""

  if [[ -n "${OUT_DIR_OVERRIDE:-}" ]]; then
    preferred_dir="${OUT_DIR_OVERRIDE%/}/aat_shim_test_logs"
  else
    preferred_dir="$ROOT/out/aat_shim_test_logs"
  fi

  if mkdir -p "$preferred_dir" >/dev/null 2>&1; then
    LOG_DIR="$preferred_dir"
  else
    if tmp_dir="$(mktemp -d "${TMP_ROOT}/aat_shim_test_logs.XXXXXX" 2>/dev/null)"; then
      LOG_DIR="$tmp_dir"
      USING_TEMP_LOG_DIR=1
    else
      echo "FAIL: unable to create log dir under '$preferred_dir' or '${TMP_ROOT}'" >&2
      exit 1
    fi
  fi

  LOG_STDOUT="$LOG_DIR/main.stdout.log"
  LOG_STDERR="$LOG_DIR/main.stderr.log"
  : >"$LOG_STDOUT" 2>/dev/null || {
    echo "FAIL: unable to write LOG_STDOUT=$LOG_STDOUT" >&2
    exit 1
  }
  : >"$LOG_STDERR" 2>/dev/null || {
    echo "FAIL: unable to write LOG_STDERR=$LOG_STDERR" >&2
    exit 1
  }
}

on_err() {
  local rc="$?"
  local had_logs=0
  {
    echo "FAIL at line ${BASH_LINENO[0]}: ${BASH_COMMAND} (exit=$rc)"
    echo "LOG_STDOUT=$LOG_STDOUT"
    echo "LOG_STDERR=$LOG_STDERR"
    if [[ -s "${LOG_STDERR:-}" ]]; then
      had_logs=1
      echo "--- LAST 200 STDERR ---"
      tail -n 200 "$LOG_STDERR" || true
    fi
    if [[ -s "${LOG_STDOUT:-}" ]]; then
      had_logs=1
      echo "--- LAST 200 STDOUT ---"
      tail -n 200 "$LOG_STDOUT" || true
    fi
    if [[ "$had_logs" -eq 0 ]]; then
      echo "LOG FILE MISSING/EMPTY"
      if [[ -n "${LAST_CAPTURE_STDERR:-}" && -f "${LAST_CAPTURE_STDERR:-}" ]]; then
        echo "LAST_CAPTURE_STDERR=$LAST_CAPTURE_STDERR"
        tail -n 200 "$LAST_CAPTURE_STDERR" || true
      fi
      if [[ -n "${LAST_CAPTURE_STDOUT:-}" && -f "${LAST_CAPTURE_STDOUT:-}" ]]; then
        echo "LAST_CAPTURE_STDOUT=$LAST_CAPTURE_STDOUT"
        tail -n 200 "$LAST_CAPTURE_STDOUT" || true
      fi
    fi
  } >&2
}
trap on_err ERR

cleanup() {
  local rc="$?"
  local f
  if [[ "$USING_TEMP_LOG_DIR" -eq 1 && "${KEEP_LOGS:-0}" != "1" && -n "$LOG_DIR" ]]; then
    rm -rf "$LOG_DIR" || true
  fi
  for f in ${CLEANUP_FILES[@]-}; do
    rm -f "$f" || true
  done
  exit "$rc"
}
trap cleanup EXIT

init_log_dir
echo "LOG_DIR=$LOG_DIR"
if [[ "$USING_TEMP_LOG_DIR" -eq 1 ]]; then
  echo "LOG_DIR_MODE=tmp_fallback"
else
  echo "LOG_DIR_MODE=repo_out"
fi

require_tool() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "FAIL: required tool missing: $1" >&2
    exit 1
  }
}

assert_file() {
  local p="$1"
  [[ -f "$p" ]] || {
    echo "FAIL: missing fixture file: $p" >&2
    exit 1
  }
}

assert_contains() {
  local pattern="$1"
  local file="$2"
  if ! rg -n --fixed-strings "$pattern" "$file" >/dev/null 2>&1; then
    echo "FAIL: expected pattern not found: $pattern in $file" >&2
    echo "--- file tail ($file) ---" >&2
    tail -n 200 "$file" >&2 || true
    exit 1
  fi
}

run_capture() {
  local label="$1"
  shift
  local out_file="$LOG_DIR/${label}.stdout.log"
  local err_file="$LOG_DIR/${label}.stderr.log"
  LAST_CAPTURE_STDOUT="$out_file"
  LAST_CAPTURE_STDERR="$err_file"
  "$@" >"$out_file" 2>"$err_file"
  cat "$out_file" >>"$LOG_STDOUT"
  cat "$err_file" >>"$LOG_STDERR"
}

run_capture_expect() {
  local label="$1"
  local expected_rc="$2"
  shift 2
  local out_file="$LOG_DIR/${label}.stdout.log"
  local err_file="$LOG_DIR/${label}.stderr.log"
  LAST_CAPTURE_STDOUT="$out_file"
  LAST_CAPTURE_STDERR="$err_file"
  set +e
  "$@" >"$out_file" 2>"$err_file"
  local rc=$?
  set -e
  cat "$out_file" >>"$LOG_STDOUT"
  cat "$err_file" >>"$LOG_STDERR"
  if [[ "$rc" -ne "$expected_rc" ]]; then
    echo "FAIL: $label expected rc=$expected_rc got rc=$rc" >&2
    echo "STDOUT_LOG=$out_file" >&2
    echo "STDERR_LOG=$err_file" >&2
    tail -n 200 "$out_file" >&2 || true
    tail -n 200 "$err_file" >&2 || true
    exit 1
  fi
}

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

copy_aat_inputs() {
  local fixture_name="$1"
  local bundle_dir="$2"
  local layout="${3:-preferred}"
  local fixture_dir="$ROOT/system/tests/fixtures/proof_bundle_with_aat_inputs/$fixture_name"
  local fixture_src_dir="$fixture_dir"
  [[ -d "$fixture_dir" ]] || {
    echo "FAIL: fixture directory missing: $fixture_dir" >&2
    exit 1
  }

  if [[ "$layout" == "preferred" && -d "$fixture_dir/aat" ]]; then
    fixture_src_dir="$fixture_dir/aat"
  fi

  assert_file "$fixture_src_dir/action_record.json"
  assert_file "$fixture_src_dir/decision_record.json"

  case "$layout" in
    preferred)
      mkdir -p "$bundle_dir/aat"
      cp "$fixture_src_dir"/*.json "$bundle_dir/aat"/
      ;;
    legacy_root)
      cp "$fixture_src_dir"/*.json "$bundle_dir"/
      ;;
    *)
      echo "FAIL: unknown layout mode: $layout" >&2
      exit 1
      ;;
  esac
}

run_single() {
  require_tool bash
  require_tool python3
  require_tool rg
  require_tool shasum

  local td
  td="$(mktemp -d "${TMPDIR:-/tmp}/aat-shim.XXXXXX")"
  trap 'rm -rf "$td"' RETURN

  local base1="$td/base1" base2="$td/base2"
  make_valid_bundle "$base1"
  make_valid_bundle "$base2"

  local o_base="$td/o_base.txt" o_disabled="$td/o_disabled.txt"
  run_capture baseline_default env AAT_SHIM_ENABLE=0 AAT_SHIM_STRICT=0 bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$base1"
  run_capture baseline_disabled env AAT_SHIM_ENABLE=0 AAT_SHIM_STRICT=0 bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$base2"
  cp "$LOG_DIR/baseline_default.stdout.log" "$o_base"
  cp "$LOG_DIR/baseline_disabled.stdout.log" "$o_disabled"
  h_base="$(shasum -a 256 "$o_base" | awk '{print $1}')"
  h_disabled="$(shasum -a 256 "$o_disabled" | awk '{print $1}')"
  [[ "$h_base" == "$h_disabled" ]]
  echo "CASE=default_disabled_unchanged PASS"

  local missing="$td/missing"
  make_valid_bundle "$missing"
  local o_missing="$td/o_missing.txt"
  run_capture shim_nonstrict_missing env AAT_SHIM_ENABLE=1 AAT_SHIM_STRICT=0 bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$missing"
  cp "$LOG_DIR/shim_nonstrict_missing.stdout.log" "$o_missing"
  assert_contains "AAT_SHIM_INPUTS=MISSING" "$o_missing"
  assert_contains "AAT_SHIM=SKIP INPUTS_MISSING" "$o_missing"
  echo "CASE=enabled_nonstrict_missing_inputs PASS"

  local pass="$td/pass"
  make_valid_bundle "$pass"
  copy_aat_inputs pass_aat_preferred "$pass" preferred
  local o_pass="$td/o_pass.txt"
  run_capture shim_strict_pass env AAT_SHIM_ENABLE=1 AAT_SHIM_STRICT=1 bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$pass"
  cp "$LOG_DIR/shim_strict_pass.stdout.log" "$o_pass"
  assert_contains "AAT_SHIM_INPUTS=FOUND path=aat" "$o_pass"
  assert_contains "AAT_SHIM_RESULT=PASS REASON_CODE=NONE LEDGER_APPENDED=YES" "$o_pass"
  echo "CASE=enabled_strict_inputs_present_pass PASS"

  local nonad="$td/nonad"
  make_valid_bundle "$nonad"
  copy_aat_inputs non_admissible_aat_preferred "$nonad" preferred
  local o_nonad="$td/o_nonad.txt"
  run_capture_expect shim_strict_nonad 1 env AAT_SHIM_ENABLE=1 AAT_SHIM_STRICT=1 bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$nonad"
  cp "$LOG_DIR/shim_strict_nonad.stdout.log" "$o_nonad"
  assert_contains "AAT_SHIM_INPUTS=FOUND path=aat" "$o_nonad"
  assert_contains "AAT_SHIM_RESULT=NON_ADMISSIBLE REASON_CODE=AAT_C1_CONTRADICTION LEDGER_APPENDED=YES" "$o_nonad"
  assert_contains "FAIL: AAT_SHIM_NON_ADMISSIBLE:AAT_C1_CONTRADICTION" "$o_nonad"
  echo "CASE=enabled_strict_inputs_present_nonad PASS"

  local legacy="$td/legacy"
  make_valid_bundle "$legacy"
  copy_aat_inputs pass "$legacy" legacy_root
  local o_legacy="$td/o_legacy.txt"
  run_capture shim_strict_legacy env AAT_SHIM_ENABLE=1 AAT_SHIM_STRICT=1 bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$legacy"
  cp "$LOG_DIR/shim_strict_legacy.stdout.log" "$o_legacy"
  assert_contains "AAT_SHIM_INPUTS=FOUND path=." "$o_legacy"
  assert_contains "AAT_SHIM_RESULT=PASS REASON_CODE=NONE LEDGER_APPENDED=YES" "$o_legacy"
  echo "CASE=enabled_strict_inputs_present_legacy_root PASS"

  echo "SHIM_TEST_STATUS=PASS"
}

normalize_log() {
  local src="$1"
  local dst="$2"
  sed -E \
    -e "s|$ROOT|<REPO_ROOT>|g" \
    -e 's|/tmp/aat_shim_test_logs\.[A-Za-z0-9._-]+|<TMP_LOG_DIR>|g' \
    -e 's|/var/folders/[^[:space:]]+/aat_shim_test_logs\.[A-Za-z0-9._-]+|<TMP_LOG_DIR>|g' \
    -e 's|/tmp/aat-shim\.[A-Za-z0-9._-]+|<TMP_BUNDLE_DIR>|g' \
    -e 's|/var/folders/[^[:space:]]+/aat-shim\.[A-Za-z0-9._-]+|<TMP_BUNDLE_DIR>|g' \
    "$src" >"$dst"
}

if [[ "${1:-}" == "--single-run" ]]; then
  MODE_SINGLE_RUN=1
  run_single
  exit 0
fi

r1_raw="$(mktemp)"
r2_raw="$(mktemp)"
r1_norm="$(mktemp)"
r2_norm="$(mktemp)"
CLEANUP_FILES+=("$r1_raw" "$r2_raw" "$r1_norm" "$r2_norm")
env AAT_SHIM_ENABLE="${AAT_SHIM_ENABLE:-}" AAT_SHIM_STRICT="${AAT_SHIM_STRICT:-}" GOV_PROFILE="${GOV_PROFILE:-dev}" bash "$0" --single-run >"$r1_raw" 2>&1
env AAT_SHIM_ENABLE="${AAT_SHIM_ENABLE:-}" AAT_SHIM_STRICT="${AAT_SHIM_STRICT:-}" GOV_PROFILE="${GOV_PROFILE:-dev}" bash "$0" --single-run >"$r2_raw" 2>&1
normalize_log "$r1_raw" "$r1_norm"
normalize_log "$r2_raw" "$r2_norm"
cat "$r1_norm"
sha1="$(shasum -a 256 "$r1_norm" | awk '{print $1}')"
sha2="$(shasum -a 256 "$r2_norm" | awk '{print $1}')"
echo "RUN1_SHA256=$sha1"
echo "RUN2_SHA256=$sha2"
if [[ "$sha1" == "$sha2" ]]; then
  echo "DETERMINISTIC=YES"
else
  echo "DETERMINISTIC=NO"
  echo "DIFF_HINT=normalized_run_logs_differ"
  diff -u "$r1_norm" "$r2_norm" | sed -n '1,80p' || true
  exit 1
fi
