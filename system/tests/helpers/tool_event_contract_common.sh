#!/usr/bin/env bash

tool_event_repo_root() {
  local script_path="$1"
  cd "$(cd "$(dirname "$script_path")/../.." && pwd)"
}

tool_event_reset_dir() {
  local dir="$1"
  rm -rf "$dir"
  mkdir -p "$dir"
}

tool_event_sha256_file() {
  local file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
    return
  fi
  shasum -a 256 "$file" | awk '{print $1}'
}

tool_event_require_equal() {
  local left="$1"
  local right="$2"
  local fail_marker="$3"
  if [[ "$left" != "$right" ]]; then
    echo "$fail_marker"
    exit 1
  fi
}

tool_event_require_contains() {
  local haystack="$1"
  local needle="$2"
  local fail_marker="$3"
  if [[ "$haystack" != *"$needle"* ]]; then
    echo "$fail_marker"
    exit 1
  fi
}

tool_event_kv_field() {
  local line="$1"
  local key="$2"
  local part
  for part in $line; do
    if [[ "$part" == "$key="* ]]; then
      printf '%s\n' "${part#*=}"
      return 0
    fi
  done
  return 1
}

tool_event_require_kv_equal() {
  local line="$1"
  local key="$2"
  local expected="$3"
  local fail_marker="$4"
  local got
  got="$(tool_event_kv_field "$line" "$key" || true)"
  if [[ "$got" != "$expected" ]]; then
    echo "$fail_marker"
    exit 1
  fi
}

tool_event_require_kv_present() {
  local line="$1"
  local key="$2"
  local fail_marker="$3"
  local got
  got="$(tool_event_kv_field "$line" "$key" || true)"
  if [[ -z "$got" ]]; then
    echo "$fail_marker"
    exit 1
  fi
}

tool_event_require_status_line() {
  local line="$1"
  local prefix="$2"
  local fail_marker="$3"
  shift 3
  if [[ "$line" != "$prefix"* ]]; then
    echo "$fail_marker"
    exit 1
  fi
  local kv
  for kv in "$@"; do
    local key="${kv%%=*}"
    local expected="${kv#*=}"
    tool_event_require_kv_equal "$line" "$key" "$expected" "$fail_marker"
  done
}

tool_event_require_deterministic_files() {
  local run1_file="$1"
  local run2_file="$2"
  local fail_marker="$3"
  local h1
  local h2
  h1="$(tool_event_sha256_file "$run1_file")"
  h2="$(tool_event_sha256_file "$run2_file")"
  tool_event_require_equal "$h1" "$h2" "$fail_marker"
  printf '%s\n%s\n' "$h1" "$h2"
}
