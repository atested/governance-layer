#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task188-locale.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

normalize_file() {
  python3 - <<'PY' "$1" "$2"
import pathlib, re, sys
src = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8', errors='replace')
root = str(pathlib.Path(sys.argv[2]).resolve())
s = src.replace(root, '<ROOT>')
s = re.sub(r'/tmp/task188-locale\.[^/]+', '/tmp/task188-locale.<TMP>', s)
s = re.sub(r'out/proof-bundles/[A-Za-z0-9._-]+', 'out/proof-bundles/<RUNID>', s)
print(s, end='' if s.endswith('\n') else '\n')
PY
}

run_and_digest() {
  local label="$1"; shift
  local outfile="$TMPDIR_LOCAL/${label}.out"
  local normfile="$TMPDIR_LOCAL/${label}.norm"
  set +e
  "$@" >"$outfile" 2>&1
  local rc=$?
  set -e
  normalize_file "$outfile" "$TMPDIR_LOCAL" >"$normfile"
  local h
  h="$(sha256_file "$normfile")"
  echo "${label}_RC=${rc}"
  echo "${label}_SHA256=${h}"
  printf '%s' "$h" > "$TMPDIR_LOCAL/${label}.sha"
  printf '%s' "$rc" > "$TMPDIR_LOCAL/${label}.rc"
}

run_once_locale() {
  local tag="$1"
  local locale_env="$2"
  local bundle="$TMPDIR_LOCAL/out/proof-bundles/task188"

  echo "--- ${tag}: validator locale invariance checks ---"
  run_and_digest "${tag}_validator_run1" env ${locale_env} bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$bundle"
  run_and_digest "${tag}_validator_run2" env ${locale_env} bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$bundle"
  [[ "$(cat "$TMPDIR_LOCAL/${tag}_validator_run1.rc")" == "0" && "$(cat "$TMPDIR_LOCAL/${tag}_validator_run2.rc")" == "0" ]] || {
    echo "FAIL: ${tag} validator rc mismatch"; exit 1;
  }
  local h1 h2
  h1="$(cat "$TMPDIR_LOCAL/${tag}_validator_run1.sha")"
  h2="$(cat "$TMPDIR_LOCAL/${tag}_validator_run2.sha")"
  echo "${tag}_VALIDATOR_SHA256_RUN1=${h1}"
  echo "${tag}_VALIDATOR_SHA256_RUN2=${h2}"
  [[ "$h1" == "$h2" ]] || { echo "FAIL: ${tag} validator output nondeterministic"; exit 1; }
  echo "PASS: ${tag} validator output deterministic"

  if [[ -x "$ROOT/tests/test_proof_bundle_dir_contract_scan_contract.sh" ]]; then
    run_and_digest "${tag}_dirscan_run1" env ${locale_env} bash "$ROOT/tests/test_proof_bundle_dir_contract_scan_contract.sh"
    run_and_digest "${tag}_dirscan_run2" env ${locale_env} bash "$ROOT/tests/test_proof_bundle_dir_contract_scan_contract.sh"
    [[ "$(cat "$TMPDIR_LOCAL/${tag}_dirscan_run1.rc")" == "0" && "$(cat "$TMPDIR_LOCAL/${tag}_dirscan_run2.rc")" == "0" ]] || {
      echo "FAIL: ${tag} dirscan contract rc mismatch"; exit 1;
    }
    h1="$(cat "$TMPDIR_LOCAL/${tag}_dirscan_run1.sha")"
    h2="$(cat "$TMPDIR_LOCAL/${tag}_dirscan_run2.sha")"
    echo "${tag}_DIRSCAN_SHA256_RUN1=${h1}"
    echo "${tag}_DIRSCAN_SHA256_RUN2=${h2}"
    [[ "$h1" == "$h2" ]] || { echo "FAIL: ${tag} dirscan contract nondeterministic"; exit 1; }
    echo "PASS: ${tag} dirscan contract output deterministic"
  else
    echo "INFO: tests/test_proof_bundle_dir_contract_scan_contract.sh missing (skip)"
    echo "SKIP: dirscan contract locale check deferred"
  fi
}

# Build a deterministic proof-bundle fixture using release-gate in a temp output dir.
RELEASE_GATE_SKIP_BASE=1 \
GOV_PROFILE=ci \
RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$TMPDIR_LOCAL/out/proof-bundles" \
RELEASE_GATE_RUN_ID="task188" \
bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/release_gate.out"

BUNDLE_DIR="$TMPDIR_LOCAL/out/proof-bundles/task188"
[[ -d "$BUNDLE_DIR" ]] || { echo "ERROR: missing bundle dir $BUNDLE_DIR"; exit 2; }

echo "--- T-EXTERNAL-LOCALE-001: locale invariance for validator + optional scanner ---"
run_once_locale C "LC_ALL=C"
run_once_locale UTF8 "LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8"

c_h="$(cat "$TMPDIR_LOCAL/C_validator_run1.sha")"
u_h="$(cat "$TMPDIR_LOCAL/UTF8_validator_run1.sha")"
echo "CROSS_LOCALE_VALIDATOR_SHA256_C=${c_h}"
echo "CROSS_LOCALE_VALIDATOR_SHA256_UTF8=${u_h}"
[[ "$c_h" == "$u_h" ]] || { echo "FAIL: validator output differs across locales"; exit 1; }
echo "PASS: validator output locale-invariant after normalization"

echo "Summary: external locale invariance regression checks complete"
