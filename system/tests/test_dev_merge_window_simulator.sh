#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SIM="$ROOT/scripts/dev_merge_window_simulator.sh"

if [[ ! -x "$SIM" ]]; then
  echo "FAIL:SIMULATOR_MISSING"
  exit 1
fi

TMP_BASE="${TMPDIR:-$ROOT/out}"
WORKDIR="$(mktemp -d "$TMP_BASE/dev_merge_window_sim.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

REPO="$WORKDIR/repo"
mkdir -p "$REPO"
cd "$REPO"

git init -q
git config user.email test@example.com
git config user.name "Test User"

BASE_BRANCH="$(git symbolic-ref --short HEAD)"

mkdir -p system/scripts docs/dev
printf 'base\n' > normal.txt
printf 'base\n' > system/scripts/release-gate.sh
printf 'base\n' > system/scripts/validate-proof-bundle.sh
printf 'base\n' > system/scripts/codex-unattended.sh
printf 'base\n' > docs/dev/WORK_QUEUE.md
printf 'base\n' > docs/dev/ASSIGNMENTS.md

git add .
git commit -q -m "base"

git checkout -q -b safe
printf 'safe\n' > normal.txt
git add normal.txt
git commit -q -m "safe change"

git checkout -q -b unsafe "$BASE_BRANCH"
printf 'unsafe\n' > system/scripts/release-gate.sh
git add system/scripts/release-gate.sh
git commit -q -m "unsafe hot file"

git checkout -q "$BASE_BRANCH"

printf 'safe\n' > "$WORKDIR/branches_safe.txt"
printf 'safe\nunsafe\n' > "$WORKDIR/branches_unsafe.txt"

normalize_file() {
  local in_file="$1"
  local out_file="$2"
  sed -E \
    -e 's#/U[s]ers/[^[:space:]]+#<ABS_PATH>#g' \
    -e 's#/V[o]lumes/[^[:space:]]+#<ABS_PATH>#g' \
    "$in_file" > "$out_file"
}

# Case 1: safe merge succeeds and completion packet exists.
set +e
bash "$SIM" \
  --repo "$REPO" \
  --mseq M_SIM_OK \
  --base "$BASE_BRANCH" \
  --branches "$WORKDIR/branches_safe.txt" \
  --test-cmd "test -f normal.txt" \
  --out-dir "$WORKDIR/out_packets" >/dev/null 2>&1
rc_ok=$?
set -e

if [[ $rc_ok -ne 0 ]]; then
  echo "FAIL:SAFE_CASE_RC=$rc_ok"
  exit 1
fi

packet_ok="$WORKDIR/out_packets/M_SIM_OK/COMPLETION_PACKET.txt"
cecil_ok="$WORKDIR/out_packets/M_SIM_OK/CECIL_DISPATCH.txt"
manifest_ok="$WORKDIR/out_packets/M_SIM_OK/MERGE_SET.json"

if [[ ! -f "$packet_ok" ]]; then
  echo "FAIL:MISSING_COMPLETION_PACKET"
  exit 1
fi
if [[ ! -f "$cecil_ok" ]]; then
  echo "FAIL:MISSING_CECIL_DISPATCH"
  exit 1
fi
if [[ ! -f "$manifest_ok" ]]; then
  echo "FAIL:MISSING_MERGE_SET"
  exit 1
fi

if ! rg -q '^FINAL_SHA=' "$packet_ok"; then
  echo "FAIL:MISSING_FINAL_SHA"
  exit 1
fi
if ! rg -q '^CECIL DISPATCH — MERGE WINDOW$' "$cecil_ok"; then
  echo "FAIL:CECIL_HEADER"
  exit 1
fi
if ! rg -q '^MSEQ:' "$cecil_ok"; then
  echo "FAIL:CECIL_MSEQ"
  exit 1
fi
if ! rg -q '^Merge set:' "$cecil_ok"; then
  echo "FAIL:CECIL_MERGE_SET"
  exit 1
fi

python3 - "$manifest_ok" <<'PY'
import json
import sys
p = sys.argv[1]
with open(p, 'r', encoding='utf-8') as f:
    obj = json.load(f)
required = ["mseq", "base_ref", "base_sha", "branches", "test_cmds", "hot_files"]
missing = [k for k in required if k not in obj]
if missing:
    print("FAIL:MANIFEST_KEYS=" + ",".join(missing))
    raise SystemExit(1)
print("CASE=MANIFEST_JSON_OK")
PY

# Case 2: unsafe branch fails preflight hot file scan and STOP packet exists.
set +e
bash "$SIM" \
  --repo "$REPO" \
  --mseq M_SIM_STOP \
  --base "$BASE_BRANCH" \
  --branches "$WORKDIR/branches_unsafe.txt" \
  --test-cmd "test -f normal.txt" \
  --out-dir "$WORKDIR/out_packets" >/dev/null 2>&1
rc_stop=$?
set -e

if [[ $rc_stop -eq 0 ]]; then
  echo "FAIL:UNSAFE_CASE_EXPECTED_FAIL"
  exit 1
fi

stop_packet="$WORKDIR/out_packets/M_SIM_STOP/STOP_PACKET.txt"
if [[ ! -f "$stop_packet" ]]; then
  echo "FAIL:MISSING_STOP_PACKET"
  exit 1
fi
if ! rg -q '^Stop Reason=HOT_FILE_VIOLATION$' "$stop_packet"; then
  echo "FAIL:STOP_REASON_MISMATCH"
  exit 1
fi

# Case 3: determinism for completion, dispatch, and manifest.
for run in 1 2; do
  rm -rf "$WORKDIR/out_packets/M_SIM_DET"
  bash "$SIM" \
    --repo "$REPO" \
    --mseq M_SIM_DET \
    --base "$BASE_BRANCH" \
    --branches "$WORKDIR/branches_safe.txt" \
    --test-cmd "test -f normal.txt" \
    --out-dir "$WORKDIR/out_packets" >/dev/null 2>&1

  normalize_file "$WORKDIR/out_packets/M_SIM_DET/COMPLETION_PACKET.txt" "$WORKDIR/packet_run${run}.txt"
  normalize_file "$WORKDIR/out_packets/M_SIM_DET/CECIL_DISPATCH.txt" "$WORKDIR/cecil_run${run}.txt"
  normalize_file "$WORKDIR/out_packets/M_SIM_DET/MERGE_SET.json" "$WORKDIR/manifest_run${run}.json"
done

sha_packet_1="$(shasum -a 256 "$WORKDIR/packet_run1.txt" | awk '{print $1}')"
sha_packet_2="$(shasum -a 256 "$WORKDIR/packet_run2.txt" | awk '{print $1}')"
sha_cecil_1="$(shasum -a 256 "$WORKDIR/cecil_run1.txt" | awk '{print $1}')"
sha_cecil_2="$(shasum -a 256 "$WORKDIR/cecil_run2.txt" | awk '{print $1}')"
sha_manifest_1="$(shasum -a 256 "$WORKDIR/manifest_run1.json" | awk '{print $1}')"
sha_manifest_2="$(shasum -a 256 "$WORKDIR/manifest_run2.json" | awk '{print $1}')"

echo "RUN1_PACKET_SHA256=$sha_packet_1"
echo "RUN2_PACKET_SHA256=$sha_packet_2"
echo "RUN1_CECIL_SHA256=$sha_cecil_1"
echo "RUN2_CECIL_SHA256=$sha_cecil_2"
echo "RUN1_MANIFEST_SHA256=$sha_manifest_1"
echo "RUN2_MANIFEST_SHA256=$sha_manifest_2"

if [[ "$sha_packet_1" != "$sha_packet_2" || "$sha_cecil_1" != "$sha_cecil_2" || "$sha_manifest_1" != "$sha_manifest_2" ]]; then
  echo "DETERMINISTIC=NO"
  exit 1
fi

echo "DETERMINISTIC=YES"
echo "CASE=DEV_MERGE_WINDOW_SIMULATOR PASS"
