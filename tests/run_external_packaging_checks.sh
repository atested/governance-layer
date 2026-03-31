#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task173-external-checks.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

run_script() {
  local script="$1"
  local label="$2"
  echo "BEGIN:$label"
  if [[ ! -f "$ROOT/$script" ]]; then
    echo "INFO: missing script $script (skip)"
    echo "END:$label rc=3"
    return 0
  fi
  if [[ "$script" == "tests/test_proof_bundle_dir_contract_scan.sh" && -z "${PROOF_BUNDLE_DIR:-}" ]]; then
    echo "INFO: PROOF_BUNDLE_DIR not set (skip $script)"
    echo "END:$label rc=3"
    return 0
  fi
  set +e
  if [[ "$script" == "tests/test_proof_bundle_dir_contract_scan.sh" ]]; then
    PROOF_BUNDLE_DIR="${PROOF_BUNDLE_DIR}" bash "$ROOT/$script" > "$TMPDIR_LOCAL/${label}.out" 2>&1
  else
    bash "$ROOT/$script" > "$TMPDIR_LOCAL/${label}.out" 2>&1
  fi
  local rc=$?
  set -e
  cat "$TMPDIR_LOCAL/${label}.out"
  echo "END:$label rc=$rc"
  if [[ $rc -ne 0 ]]; then
    OVERALL_RC=1
  fi
}

run_once() {
  local out="$1"
  local tmp="$TMPDIR_LOCAL/run_once.tmp"
  OVERALL_RC=0
  : > "$tmp"
  {
    echo "--- T-EXTERNAL-CHECKS-001: bounded cold-surface external checks runner ---"
    run_script tests/test_repo_packaging_check.sh TASK165
    run_script tests/test_external_packaging_smoke.sh TASK168
    if [[ "${EXTERNAL_CHECKS_SKIP_GHA:-0}" == "1" ]]; then
      echo "BEGIN:TASK169"
      echo "INFO: EXTERNAL_CHECKS_SKIP_GHA=1 (skip TASK169)"
      echo "END:TASK169 rc=3"
    else
      run_script tests/test_github_actions_release_gate_artifacts_completeness.sh TASK169
    fi
    run_script tests/test_external_docs_contract_consistency.sh TASK171
    run_script tests/test_forbidden_repo_artifacts.sh TASK172
    if [[ -n "${PROOF_BUNDLE_DIR:-}" ]]; then
      run_script tests/test_proof_bundle_dir_contract_scan.sh TASK170
    else
      echo "INFO: PROOF_BUNDLE_DIR not set (TASK170 optional in meta-runner)"
    fi
    echo "META_RUNNER_RC=$OVERALL_RC"
    if [[ $OVERALL_RC -eq 0 ]]; then
      echo "PASS: external packaging checks meta-runner complete"
    else
      echo "FAIL: external packaging checks meta-runner detected failing subchecks"
    fi
  } > "$tmp"
  cat "$tmp" | tee "$out"

  return "$OVERALL_RC"
}

set +e
run_once "$TMPDIR_LOCAL/run1.out"
RC1=$?
run_once "$TMPDIR_LOCAL/run2.out"
RC2=$?
set -e
H1="$(sha256_file "$TMPDIR_LOCAL/run1.out")"
H2="$(sha256_file "$TMPDIR_LOCAL/run2.out")"
echo "EXTERNAL_CHECKS_META_RC_RUN1=$RC1"
echo "EXTERNAL_CHECKS_META_RC_RUN2=$RC2"
echo "EXTERNAL_CHECKS_META_SHA256_RUN1=$H1"
echo "EXTERNAL_CHECKS_META_SHA256_RUN2=$H2"
[[ "$H1" == "$H2" ]] || { echo "FAIL: meta-runner output nondeterministic"; exit 1; }
echo "PASS: external packaging meta-runner output deterministic across two runs"
[[ "$RC1" -eq "$RC2" ]] || { echo "FAIL: meta-runner rc differs across runs"; exit 1; }
[[ "$RC1" -eq 0 ]] && exit 0
exit 1
