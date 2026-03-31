#!/usr/bin/env bash

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tool_event_contract_common.sh"

tool_event_receipt_replay_repo_root() {
  tool_event_repo_root "$1"
}

tool_event_receipt_replay_reset() {
  local tmp_root="$1"
  local result_dir="$2"
  rm -rf "$tmp_root" "$result_dir" out/mcp_exec out/mcp_ingest_tool_event
  mkdir -p "$tmp_root" "$result_dir"
}

tool_event_receipt_replay_require_deterministic_files() {
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
