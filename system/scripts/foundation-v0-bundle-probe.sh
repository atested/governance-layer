#!/usr/bin/env bash
set -euo pipefail

bundle_dir="${1:-}"
if [[ -z "$bundle_dir" ]]; then
  echo "usage: system/scripts/foundation-v0-bundle-probe.sh <proof_bundle_dir>"
  exit 2
fi

if [[ ! -d "$bundle_dir" ]]; then
  echo "MANIFEST_PATH=NOT_FOUND"
  echo "DETECTED_SURFACES="
  echo "LEDGER_PATH=NOT_FOUND"
  exit 1
fi

manifest_path=""
for p in "$bundle_dir/proof_manifest.json" "$bundle_dir/manifest.json"; do
  if [[ -f "$p" ]]; then
    manifest_path="$p"
    break
  fi
done
[[ -n "$manifest_path" ]] || manifest_path="NOT_FOUND"

ledger_path=""
for p in "$bundle_dir/ledger.jsonl" "$bundle_dir/process_ledger.jsonl"; do
  if [[ -f "$p" ]]; then
    ledger_path="$p"
    break
  fi
done
[[ -n "$ledger_path" ]] || ledger_path="NOT_FOUND"

surfaces=""
if [[ "$ledger_path" != "NOT_FOUND" ]]; then
  surfaces="$(python3 - <<'PY' "$ledger_path"
import json,sys
vals=set()
for line in open(sys.argv[1], encoding='utf-8'):
  line=line.strip()
  if not line:
    continue
  obj=json.loads(line)
  for s in obj.get('capability_surfaces',[]):
    vals.add(s)
print(','.join(sorted(vals)))
PY
)"
fi

echo "MANIFEST_PATH=$manifest_path"
echo "DETECTED_SURFACES=$surfaces"
echo "LEDGER_PATH=$ledger_path"
