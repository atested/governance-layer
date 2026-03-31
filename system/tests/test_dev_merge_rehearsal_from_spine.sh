#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP="out/test_dev_merge_rehearsal_from_spine"
BRANCHES_FILE="$TMP/branches.txt"
RUN1="$TMP/run1.txt"
RUN2="$TMP/run2.txt"

rm -rf "$TMP"
mkdir -p "$TMP"

printf 'MERGE_SIM_INPUTS_EMPTY=YES\n' > "$BRANCHES_FILE"

bash scripts/dev_merge_rehearsal_from_spine.sh --branches-file "$BRANCHES_FILE" > "$RUN1"
bash scripts/dev_merge_rehearsal_from_spine.sh --branches-file "$BRANCHES_FILE" > "$RUN2"

H1="$(shasum -a 256 "$RUN1" | awk '{print $1}')"
H2="$(shasum -a 256 "$RUN2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

grep -qx 'MERGE_REHEARSAL_SKIPPED=NO_BRANCHES' "$RUN1"

echo "CASE=DEV_MERGE_REHEARSAL_FROM_SPINE PASS"
