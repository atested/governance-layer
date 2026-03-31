#!/bin/bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: audit_artifact_helper.sh <path> [path...]" >&2
  exit 2
fi

for f in "$@"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING:$f"
    exit 1
  fi
done

LC_ALL=C printf '%s\n' "$@" | LC_ALL=C sort | while IFS= read -r file; do
  sha=$(shasum -a 256 "$file" | awk '{print $1}')
  lines=$(wc -l < "$file" | tr -d ' ')
  echo "$sha|$lines|$file"
done
