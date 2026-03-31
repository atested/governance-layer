#!/usr/bin/env bash
set -euo pipefail

OUT="docs/dev/inventory/INVENTORY_LATEST.md"
mkdir -p "$(dirname "$OUT")"

# No timestamps allowed in OUT. Deterministic ordering only.

echo "# Inventory Latest" > "$OUT"
echo "" >> "$OUT"

echo "## Repo" >> "$OUT"
echo "" >> "$OUT"
echo "- Top: $(git rev-parse --show-toplevel)" >> "$OUT"
echo "- Branch: $(git rev-parse --abbrev-ref HEAD)" >> "$OUT"
echo "" >> "$OUT"

echo "## Remotes" >> "$OUT"
echo "" >> "$OUT"
git remote -v | sort >> "$OUT"
echo "" >> "$OUT"

echo "## system/scripts index" >> "$OUT"
echo "" >> "$OUT"
if [ -d system/scripts ]; then
  ls -1 system/scripts | sort | while read -r f; do
    if [ -f "system/scripts/$f" ]; then
      # Prefer first comment line as purpose hint, else filename only.
      first_line="$(head -n 1 "system/scripts/$f" | tr -d '\r')"
      if echo "$first_line" | grep -qE '^(#|//)'; then
        echo "- $f — ${first_line#\# }" >> "$OUT"
        echo "- $f — ${first_line#// }" >> "$OUT" 2>/dev/null || true
      else
        echo "- $f" >> "$OUT"
      fi
    fi
  done
fi
echo "" >> "$OUT"

echo "## Keyword detections" >> "$OUT"
echo "" >> "$OUT"
echo "### WORK_QUEUE / claim / merge / ASSIGNMENTS behaviors" >> "$OUT"
echo "" >> "$OUT"
grep -Rni --exclude-dir=.git --exclude='*.log' -E \
  'WORK_QUEUE|queue-claim|claim|merge-queue|git merge|checkout main|ASSIGNMENTS\.md|Auto-resolving ASSIGNMENTS' \
  system/scripts 2>/dev/null | sort >> "$OUT" || true
echo "" >> "$OUT"

echo "## Tasks (ready)" >> "$OUT"
echo "" >> "$OUT"
if [ -d docs/dev/tasks/ready ]; then
  ls -1 docs/dev/tasks/ready | sort | sed -n '1,100p' >> "$OUT"
fi
echo "" >> "$OUT"

echo "## Evidence directories" >> "$OUT"
echo "" >> "$OUT"
if [ -d docs/dev/evidence ]; then
  find docs/dev/evidence -maxdepth 2 -type d -name 'TASK_*' -o -name 'OPS_CANONICAL' 2>/dev/null | sort | sed -n '1,100p' >> "$OUT" || true
fi
echo "" >> "$OUT"

echo "## Policy reason codes (RC-FS-*)" >> "$OUT"
echo "" >> "$OUT"
if [ -f scripts/policy-eval.py ]; then
  grep -nE 'RC_[A-Z0-9_]+\s*=\s*"RC-FS-' scripts/policy-eval.py | sed 's/^/- /' >> "$OUT" || true
fi
echo "" >> "$OUT"

echo "## Potential contradictions" >> "$OUT"
echo "" >> "$OUT"
echo "- Scripts that appear to merge or touch main (must be classified in OPS_CANONICAL):" >> "$OUT"
echo "" >> "$OUT"
grep -Rni --exclude-dir=.git --exclude='*.log' -E 'git merge|checkout main|reset --hard origin/main' system/scripts 2>/dev/null | sort | sed 's/^/- /' >> "$OUT" || true
