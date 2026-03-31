#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PASS_FIXTURE="$SCRIPT_DIR/fixtures/aat/golden_pass/tool_exec_profile"
FAIL_C1_FIXTURE="$SCRIPT_DIR/fixtures/aat/golden_fail/tool_exec_profile_c1_enforced"
FAIL_C2_FIXTURE="$SCRIPT_DIR/fixtures/aat/golden_fail/tool_exec_profile_c2_enforced"

require_fixture() {
  local dir="$1"
  [[ -d "$dir" ]] || {
    echo "FAIL: missing fixture directory: $dir" >&2
    exit 1
  }
}

run_case_twice() {
  local label="$1"
  local expected_rc="$2"
  local expect_decision="$3"
  local expect_reason="$4"
  shift 4

  local out1 out2 rc1 rc2 h1 h2
  out1="$(mktemp)"
  out2="$(mktemp)"

  set +e
  "$@" >"$out1" 2>&1
  rc1=$?
  "$@" >"$out2" 2>&1
  rc2=$?
  set -e

  if [[ "$rc1" -ne "$expected_rc" || "$rc2" -ne "$expected_rc" ]]; then
    echo "FAIL: $label rc mismatch expected=$expected_rc got=run1:$rc1 run2:$rc2"
    tail -n 120 "$out1" || true
    tail -n 120 "$out2" || true
    exit 1
  fi

  rg -n --fixed-strings "$expect_decision" "$out1" >/dev/null
  if [[ "$expect_reason" != "NONE" ]]; then
    rg -n --fixed-strings "$expect_reason" "$out1" >/dev/null
  fi

  h1="$(shasum -a 256 "$out1" | awk '{print $1}')"
  h2="$(shasum -a 256 "$out2" | awk '{print $1}')"
  if [[ "$h1" != "$h2" ]]; then
    echo "FAIL: $label nondeterministic output"
    echo "RUN1_SHA256=$h1"
    echo "RUN2_SHA256=$h2"
    diff -u "$out1" "$out2" | sed -n '1,80p' || true
    exit 1
  fi

  echo "CASE=${label} PASS"
  echo "CASE=${label} RUN1_SHA256=$h1"
  echo "CASE=${label} RUN2_SHA256=$h2"
  rm -f "$out1" "$out2"
}

main() {
  require_fixture "$PASS_FIXTURE"
  require_fixture "$FAIL_C1_FIXTURE"
  require_fixture "$FAIL_C2_FIXTURE"

  # Default behavior remains CORE_GENERIC.
  run_case_twice \
    "default_core_generic_c1_is_report_only" \
    0 \
    '"decision":"PASS"' \
    "AAT_C1_CONTRADICTION_DETECTED" \
    python3 "$REPO_ROOT/scripts/aat_main.py" \
      --bundle-dir "$FAIL_C1_FIXTURE" \
      --schema-dir "$REPO_ROOT/system/schemas"

  # Explicit profile selection must enforce TOOL_EXEC profile.
  run_case_twice \
    "explicit_tool_exec_c1_enforced" \
    1 \
    '"decision":"FAIL_NON_ADMISSIBLE"' \
    "AAT_C1_CONTRADICTION_DETECTED" \
    python3 "$REPO_ROOT/scripts/aat_main.py" \
      --bundle-dir "$FAIL_C1_FIXTURE" \
      --schema-dir "$REPO_ROOT/system/schemas" \
      --profile TOOL_EXEC

  run_case_twice \
    "explicit_tool_exec_c2_enforced" \
    1 \
    '"decision":"FAIL_NON_ADMISSIBLE"' \
    "AAT_C2_EVIDENCE_REF_NOT_IN_IM" \
    python3 "$REPO_ROOT/scripts/aat_main.py" \
      --bundle-dir "$FAIL_C2_FIXTURE" \
      --schema-dir "$REPO_ROOT/system/schemas" \
      --profile TOOL_EXEC

  run_case_twice \
    "explicit_tool_exec_pass" \
    0 \
    '"decision":"PASS"' \
    "NONE" \
    python3 "$REPO_ROOT/scripts/aat_main.py" \
      --bundle-dir "$PASS_FIXTURE" \
      --schema-dir "$REPO_ROOT/system/schemas" \
      --profile TOOL_EXEC

  # Validate wrapper forwards profile deterministically.
  run_case_twice \
    "wrapper_profile_forwarding_c1" \
    1 \
    "ADMISSIBLE=NO" \
    "REASON_CODE=AAT_C1_CONTRADICTION_DETECTED" \
    bash "$REPO_ROOT/system/scripts/aat-admissibility-gate.sh" \
      --action-bundle-dir "$FAIL_C1_FIXTURE" \
      --repo-root "$REPO_ROOT" \
      --schema-dir "$REPO_ROOT/system/schemas" \
      --profile TOOL_EXEC

  # Unknown profile is fail-closed.
  run_case_twice \
    "unknown_profile_fail_closed" \
    2 \
    "ERROR: unknown profile=NOT_A_PROFILE" \
    "NONE" \
    python3 "$REPO_ROOT/scripts/aat_main.py" \
      --bundle-dir "$PASS_FIXTURE" \
      --schema-dir "$REPO_ROOT/system/schemas" \
      --profile NOT_A_PROFILE

  echo "PROFILE_EXPANSION_STATUS=PASS"
}

main "$@"
