#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task172-forbidden-artifacts.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

run_once() {
  local out="$1"
  (
    cd "$ROOT"
    echo "--- T-FORBIDDEN-ARTIFACTS-001: tracked files exclude local/runtime artifacts ---"
    local -a bad=()
    while IFS= read -r f; do
      case "$f" in
        out/proof-bundles/*|out/proof-bundles|.venv/*|.venv|*.swp|.DS_Store|*/.DS_Store|__pycache__/*|*/__pycache__/*)
          bad+=("$f")
          ;;
      esac
    done < <(git ls-files | LC_ALL=C sort)
    if ((${#bad[@]})); then
      printf 'FAIL: forbidden tracked artifact: %s\n' "${bad[@]}"
      exit 1
    fi
    echo "PASS: no forbidden tracked artifacts"
  ) | tee "$out"
}

run_once "$TMPDIR_LOCAL/run1.out"
run_once "$TMPDIR_LOCAL/run2.out"
H1="$(sha256_file "$TMPDIR_LOCAL/run1.out")"
H2="$(sha256_file "$TMPDIR_LOCAL/run2.out")"
echo "FORBIDDEN_ARTIFACTS_SHA256_RUN1=$H1"
echo "FORBIDDEN_ARTIFACTS_SHA256_RUN2=$H2"
[[ "$H1" == "$H2" ]] || { echo "FAIL: forbidden artifacts scanner nondeterministic"; exit 1; }
echo "PASS: forbidden artifacts scanner output deterministic across two runs"
