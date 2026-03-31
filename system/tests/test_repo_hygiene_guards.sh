#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# Conflict markers in tracked files only.
if git grep -n -E '^(<<<<<<< .+|=======$|>>>>>>> .+)$' -- . >/tmp/repo_hygiene_conflicts.txt 2>/dev/null; then
  echo "FAIL:CONFLICT_MARKERS_PRESENT"
  exit 1
fi

# Clean-tree invariant: allow only ?? out/
status="$(git status --porcelain)"
if [[ -n "$status" ]]; then
  bad="$(printf '%s\n' "$status" | awk '$0 !~ /^\?\? out\// && $0 !~ /^(\?\?| M|M |A |AM|MM) system\/tests\/test_repo_hygiene_guards\.sh$/ {print}')"
  if [[ -n "$bad" ]]; then
    echo "FAIL:DIRTY_TREE"
    exit 1
  fi
fi

# Best-effort hot file warning (non-failing).
hot_warn=0
for f in \
  system/scripts/release-gate.sh \
  system/scripts/validate-proof-bundle.sh \
  system/scripts/codex-unattended.sh \
  docs/dev/WORK_QUEUE.md \
  docs/dev/ASSIGNMENTS.md; do
  if [[ -n "$(git status --porcelain -- "$f")" ]]; then
    hot_warn=1
  fi
done

if [[ "$hot_warn" -eq 1 ]]; then
  echo "WARN:HOT_FILES_MODIFIED"
else
  echo "WARN:HOT_FILES_MODIFIED=NO"
fi

echo "CASE=REPO_HYGIENE_GUARDS PASS"
