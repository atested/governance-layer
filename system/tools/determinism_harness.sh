#!/bin/bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: determinism_harness.sh <file> [file...]" >&2
  exit 2
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

normalize_file() {
  local input="$1"
  sed -E \
    -e 's#/var/folders/[^[:space:]]+#<TMP_PATH>#g' \
    -e 's#/tmp/[^[:space:]]+#<TMP_PATH>#g' \
    -e 's#([[:space:]]+)$##' "$input"
}

for f in "$@"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING_FILE:$f" >&2
    exit 1
  fi
  normalize_file "$f" > "$tmp"
  sha=$(shasum -a 256 "$tmp" | awk '{print $1}')
  echo "$sha  $f"
done
