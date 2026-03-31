#!/usr/bin/env bash

attest_repo_root() {
  local script_path="$1"
  cd "$(cd "$(dirname "$script_path")/../.." && pwd)"
}

attest_reset_work_dir() {
  local dir="$1"
  rm -rf "$dir"
  mkdir -p "$dir"
}

attest_sha256_file() {
  local file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
    return
  fi
  shasum -a 256 "$file" | awk '{print $1}'
}

attest_require_equal() {
  local left="$1"
  local right="$2"
  local fail_marker="$3"
  if [[ "$left" != "$right" ]]; then
    echo "$fail_marker"
    exit 1
  fi
}

attest_require_deterministic_files() {
  local run1_file="$1"
  local run2_file="$2"
  local fail_marker="$3"
  local h1
  local h2
  h1="$(attest_sha256_file "$run1_file")"
  h2="$(attest_sha256_file "$run2_file")"
  attest_require_equal "$h1" "$h2" "$fail_marker"
  printf '%s\n%s\n' "$h1" "$h2"
}
