#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: evidence_bundle_indexer.sh <evidence_dir>" >&2
  exit 2
fi

root="$1"
if [[ ! -d "$root" ]]; then
  echo "missing evidence dir: $root" >&2
  exit 1
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
find "$root" -type f | LC_ALL=C sort > "$tmp"

echo '{'
echo '  "files": ['
first=1
while IFS= read -r file; do
  rel="${file#$root/}"
  sha=$(shasum -a 256 "$file" | awk '{print $1}')
  bytes=$(wc -c < "$file" | tr -d ' ')
  if [[ $first -eq 0 ]]; then
    echo '    ,'
  fi
  first=0
  echo "    {\"path\":\"$rel\",\"sha256\":\"$sha\",\"bytes\":$bytes}"
done < "$tmp"
echo '  ]'
echo '}'
