#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
TEST_KEY_FILE="$ROOT/system/tests/fixtures/keys/ed25519_test_private.pem"
HELPER="$ROOT/tests/helpers/signing_key_probe.py"
TMPDIR=$(mktemp -d)
cleanup(){ rm -rf "$TMPDIR"; }
trap cleanup EXIT

test_home="$TMPDIR/home"
mkdir -p "$test_home/.config/gov-layer"

expected_fatal="FATAL: cryptography module required for signing but not installed"
key_path="$TMPDIR/key.pem"
cp "$TEST_KEY_FILE" "$key_path"

run_probe(){
  local env_args=("HOME=$test_home" "$@")
  local rc output
  set +e
  output=$(env "${env_args[@]}" python3 "$HELPER")
  rc=$?
  set -e
  printf '%s\n' "$output"
  return $rc
}

parse_field(){
  local key="$1"
  local output="$2"
  echo "$output" | grep "^$key=" | cut -d'=' -f2-
}

run_case(){
  local label="$1"
  local expected_rc="$2"
  local expected_fatal="$3"
  shift 3
  echo "$label"
  local output
  set +e
  output=$(run_probe "$@")
  local rc=$?
  set -e
  local mode rc_line fatal
  mode=$(parse_field MODE "$output")
  rc_line=$(parse_field RC "$output")
  fatal=$(parse_field FATAL "$output")
  [[ "$rc" -eq "$expected_rc" ]]
  [[ "$rc_line" == "$rc" ]]
  if [[ "$expected_fatal" == "" ]]; then
    [[ -z "$fatal" ]]
  else
    [[ "$fatal" == "$expected_fatal" ]]
  fi
}

case_a="-- A: no key configured"
case_b="-- B: GOV_SIGNING_KEY_PATH configured"
case_c="-- C: default key exists"

run_case "$case_a" 0 ""
run_case "$case_b" 1 "$expected_fatal" "GOV_SIGNING_KEY_PATH=$key_path"
cp "$key_path" "$test_home/.config/gov-layer/signing.key"
run_case "$case_c" 1 "$expected_fatal"

echo "Summary complete"
