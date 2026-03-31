#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_DIR="out/test_merge_sim_inputs_from_queue"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

QUEUE="$TMP_DIR/D_merge_prep_queue.md"
EVID="$TMP_DIR/_merge_prep_evidence.txt"
OUT1="$TMP_DIR/branches_run1.txt"
OUT2="$TMP_DIR/branches_run2.txt"

cat > "$QUEUE" <<'MD'
# Queue
1) merge origin/codex/BRANCH_B first
2) then origin/codex/BRANCH_A
# comment line
MD

cat > "$EVID" <<'TXT'
recent refs:
origin/codex/BRANCH_C
origin/cecil/BRANCH_Z
TXT

bash scripts/dev_merge_sim_inputs_from_queue.sh \
  --queue-file "$QUEUE" \
  --evidence-file "$EVID" \
  --out-file "$OUT1" >/dev/null

bash scripts/dev_merge_sim_inputs_from_queue.sh \
  --queue-file "$QUEUE" \
  --evidence-file "$EVID" \
  --out-file "$OUT2" >/dev/null

HASH1="$(shasum -a 256 "$OUT1" | awk '{print $1}')"
HASH2="$(shasum -a 256 "$OUT2" | awk '{print $1}')"
if [[ "$HASH1" != "$HASH2" ]]; then
  echo "FAIL:NON_DETERMINISTIC"
  exit 1
fi

lines=()
while IFS= read -r line; do
  lines+=("$line")
done < "$OUT1"

if [[ "${#lines[@]}" -ne 4 ]]; then
  echo "FAIL:COUNT"
  exit 1
fi

[[ "${lines[0]}" == "origin/codex/BRANCH_B" ]] || { echo "FAIL:ORDER_0"; exit 1; }
[[ "${lines[1]}" == "origin/codex/BRANCH_A" ]] || { echo "FAIL:ORDER_1"; exit 1; }
[[ "${lines[2]}" == "origin/cecil/BRANCH_Z" ]] || { echo "FAIL:ORDER_2"; exit 1; }
[[ "${lines[3]}" == "origin/codex/BRANCH_C" ]] || { echo "FAIL:ORDER_3"; exit 1; }

echo "CASE=MERGE_SIM_INPUTS_FROM_QUEUE PASS"
