#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"
cd "$ROOT"

IDENTITY_FILE="$ROOT/PROJECT_IDENTITY.md"
OPS_CANONICAL_FILE="$ROOT/docs/dev/OPS_CANONICAL.md"
WORK_QUEUE_FILE="$ROOT/docs/dev/WORK_QUEUE.md"
CLAUDE_SETTINGS_FILE="$ROOT/.claude/settings.json"

FAILURES=0
TOTAL=8

pass() {
  printf 'PASS %s: %s\n' "$1" "$2"
}

fail() {
  printf 'FAIL %s: %s\n' "$1" "$2"
  FAILURES=$((FAILURES + 1))
}

trim() {
  sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

extract_identity_field() {
  local field="$1"
  awk -F'|' -v target="$field" '
    function trim(s) {
      sub(/^[[:space:]]+/, "", s)
      sub(/[[:space:]]+$/, "", s)
      return s
    }
    {
      if (NF < 3) next
      key = trim($2)
      val = trim($3)
      if (key == target) {
        print val
        exit
      }
    }
  ' "$IDENTITY_FILE"
}

repo_dir_name="$(basename "$ROOT")"

project_name=""
project_scope=""
governing_operator=""
bootstrap_protocol_version=""
bootstrap_timestamp_utc=""
repo_root_value=""
repo_remote=""
seed_source_reference=""

if [[ ! -f "$IDENTITY_FILE" ]]; then
  fail "T1" "PROJECT_IDENTITY.md missing"
else
  project_name="$(extract_identity_field "project_name" | trim)"
  project_scope="$(extract_identity_field "project_scope" | trim)"
  governing_operator="$(extract_identity_field "governing_operator" | trim)"
  bootstrap_protocol_version="$(extract_identity_field "bootstrap_protocol_version" | trim)"
  bootstrap_timestamp_utc="$(extract_identity_field "bootstrap_timestamp_utc" | trim)"
  repo_root_value="$(extract_identity_field "repo_root" | trim)"
  repo_remote="$(extract_identity_field "repo_remote" | trim)"
  seed_source_reference="$(extract_identity_field "seed_source_reference" | trim)"

  missing_fields=()
  [[ -n "$project_name" ]] || missing_fields+=("project_name")
  [[ -n "$project_scope" ]] || missing_fields+=("project_scope")
  [[ -n "$governing_operator" ]] || missing_fields+=("governing_operator")
  [[ -n "$bootstrap_protocol_version" ]] || missing_fields+=("bootstrap_protocol_version")
  [[ -n "$bootstrap_timestamp_utc" ]] || missing_fields+=("bootstrap_timestamp_utc")
  [[ -n "$repo_root_value" ]] || missing_fields+=("repo_root")
  [[ -n "$repo_remote" ]] || missing_fields+=("repo_remote")
  [[ -n "$seed_source_reference" ]] || missing_fields+=("seed_source_reference")

  if [[ ${#missing_fields[@]} -eq 0 ]]; then
    pass "T1" "PROJECT_IDENTITY.md present with all required non-empty fields"
  else
    fail "T1" "PROJECT_IDENTITY.md missing required field(s): ${missing_fields[*]}"
  fi
fi

if [[ -n "$project_name" && "$project_name" == "$repo_dir_name" ]]; then
  pass "T2" "project_name matches repo directory name"
else
  fail "T2" "project_name '$project_name' does not match repo directory '$repo_dir_name'"
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  remote_match="no"
  while IFS= read -r remote_name; do
    remote_url="$(git remote get-url "$remote_name" 2>/dev/null || true)"
    if [[ -n "$repo_remote" && "$remote_url" == "$repo_remote" ]]; then
      remote_match="yes"
      break
    fi
  done < <(git remote)

  if [[ "$remote_match" == "yes" ]]; then
    pass "T3" "git repository present and remote matches repo_remote"
  else
    fail "T3" "no git remote matches repo_remote '$repo_remote'"
  fi
else
  fail "T3" "not a git repository"
fi

if git rev-parse --verify main >/dev/null 2>&1; then
  main_commit_count="$(git rev-list --count main)"
  if [[ "$main_commit_count" -ge 2 ]]; then
    pass "T4" "main has at least 2 commits"
  else
    fail "T4" "main has only $main_commit_count commit(s)"
  fi
else
  fail "T4" "main branch missing"
fi

universal_files=(
  "docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md"
  "docs/dev/AGENT_CONTRACT.md"
  "docs/dev/BRIEFING_FORMAT__BFPS_v12.md"
  "docs/dev/TASK_TEMPLATE.md"
  "docs/dev/INGESTION_WORKFLOW.md"
  "docs/dev/RUNBOOK.md"
  ".claude/agents/haiku-worker.md"
  ".claude/agents/sonnet-worker.md"
)

missing_universal=()
for rel in "${universal_files[@]}"; do
  if [[ ! -s "$ROOT/$rel" ]]; then
    missing_universal+=("$rel")
  fi
done
if [[ ${#missing_universal[@]} -eq 0 ]]; then
  pass "T5" "all 8 universal dev-process files exist and are non-empty"
else
  fail "T5" "missing or empty universal file(s): ${missing_universal[*]}"
fi

if [[ -f "$OPS_CANONICAL_FILE" ]]; then
  if [[ -n "$project_name" ]] && grep -Fq "$project_name" "$OPS_CANONICAL_FILE"; then
    pass "T6" "OPS_CANONICAL.md exists and contains project_name"
  else
    fail "T6" "OPS_CANONICAL.md missing project_name '$project_name'"
  fi
else
  fail "T6" "docs/dev/OPS_CANONICAL.md missing"
fi

if [[ ! -f "$CLAUDE_SETTINGS_FILE" ]]; then
  fail "T7" ".claude/settings.json missing"
else
  if command -v python3 >/dev/null 2>&1; then
    if python3 -m json.tool "$CLAUDE_SETTINGS_FILE" >/dev/null 2>&1; then
      pass "T7" ".claude/settings.json exists and is valid JSON"
    else
      fail "T7" ".claude/settings.json is not valid JSON"
    fi
  elif command -v jq >/dev/null 2>&1; then
    if jq empty "$CLAUDE_SETTINGS_FILE" >/dev/null 2>&1; then
      pass "T7" ".claude/settings.json exists and is valid JSON"
    else
      fail "T7" ".claude/settings.json is not valid JSON"
    fi
  else
    fail "T7" "no standard JSON validation tool available (python3 or jq)"
  fi
fi

if [[ -f "$WORK_QUEUE_FILE" ]]; then
  pass "T8" "docs/dev/WORK_QUEUE.md exists"
else
  fail "T8" "docs/dev/WORK_QUEUE.md missing"
fi

if [[ "$FAILURES" -eq 0 ]]; then
  printf 'SUMMARY PASS: all %d core activation tests passed\n' "$TOTAL"
  exit 0
fi

printf 'SUMMARY FAIL: %d of %d core activation tests failed\n' "$FAILURES" "$TOTAL"
exit 1
