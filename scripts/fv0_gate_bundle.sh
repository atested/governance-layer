#!/usr/bin/env bash
set -euo pipefail

bundle_dir="${1:-}"
ledger_path="${2:-}"

if [[ -z "$bundle_dir" ]]; then
  echo "usage: scripts/fv0_gate_bundle.sh <proof_bundle_dir> [ledger_path]"
  exit 2
fi

if [[ -z "$ledger_path" ]]; then
  if [[ -f "$bundle_dir/ledger.jsonl" ]]; then
    ledger_path="$bundle_dir/ledger.jsonl"
  elif [[ -f "$bundle_dir/process_ledger.jsonl" ]]; then
    ledger_path="$bundle_dir/process_ledger.jsonl"
  fi
fi

cmd=(system/scripts/foundation-v0-admissibility-gate.sh --proof-bundle-dir "$bundle_dir")
if [[ -n "$ledger_path" ]]; then
  cmd+=(--ledger-path "$ledger_path")
fi

"${cmd[@]}"
