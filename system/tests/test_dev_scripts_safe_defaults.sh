#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

scripts=()
while IFS= read -r line; do
  [[ -n "$line" ]] || continue
  scripts+=("$line")
done <<EOF
$(git ls-files 'scripts/dev_*.sh' 'scripts/dev_*.py' | sort)
EOF

if [[ "${#scripts[@]}" -eq 0 ]]; then
  echo "CASE=NO_DEV_SCRIPTS_FOUND PASS"
  exit 0
fi

# Legacy scripts that may not have uniform help output yet.
legacy_allow_re='^scripts/dev/precommit-guard-assignments\.sh$'

fail=0
for s in "${scripts[@]}"; do
  if [[ "$s" =~ $legacy_allow_re ]]; then
    echo "WARN:LEGACY_ALLOWLIST:$s"
    continue
  fi

  runner=(bash "$s")
  if [[ "$s" == *.py ]]; then
    runner=(python3 "$s")
  fi

  set +e
  out_h="$("${runner[@]}" --help 2>&1)"
  rc_h=$?
  set -e

  if [[ $rc_h -ne 0 && $rc_h -ne 1 ]]; then
    echo "FAIL:HELP_RC:$s"
    fail=1
    continue
  fi

  if ! printf '%s\n' "$out_h" | rg -qi 'usage|help'; then
    set +e
    out_h2="$("${runner[@]}" -h 2>&1)"
    rc_h2=$?
    set -e
    if [[ $rc_h2 -ne 0 && $rc_h2 -ne 1 ]]; then
      echo "FAIL:HELP_RC_SHORT:$s"
      fail=1
      continue
    fi
    if ! printf '%s\n' "$out_h2" | rg -qi 'usage|help'; then
      echo "FAIL:HELP_TEXT:$s"
      fail=1
      continue
    fi
  fi

  echo "CHECK=PASS:$s"
done

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

echo "CASE=DEV_SCRIPTS_SAFE_DEFAULTS PASS"
