#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

git ls-files -z | xargs -0 rg -n -H '[[:blank:]]$' > "$tmp" || true
if [[ ! -s "$tmp" ]]; then
  echo "CASE=NO_TRAILING_WHITESPACE PASS"
  exit 0
fi

# Legacy allowlist for known trailing-whitespace files at baseline.
ALLOW_RE='^(\.github/workflows/guard-assignments\.yml|docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1\.md|ops/CODEX_BATCH\.txt|scripts/dev/precommit-guard-assignments\.sh|scripts/make-report\.sh|scripts/task_scaffold\.py|system/scripts/cecil-runloop\.sh|system/scripts/codex-batch\.sh|system/scripts/enforce-task-scope\.sh|system/scripts/merge-queue\.sh|system/scripts/queue-list-next\.sh|system/tests/test_determinism_harness\.sh|docs/dev/evidence/|LOGS/)'
awk -F: '{print $1":"$2}' "$tmp" | sort -u | while IFS= read -r fl; do
  f="${fl%%:*}"
  if [[ ! "$f" =~ $ALLOW_RE ]]; then
    echo "$fl"
  fi
done | sort -u > "$tmp.bad"

if [[ -s "$tmp.bad" ]]; then
  cat "$tmp.bad"
  echo "FAIL:TRAILING_WHITESPACE_FOUND"
  exit 1
fi

echo "CASE=NO_TRAILING_WHITESPACE PASS"
