#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_dev_merge_rehearsal_integration"
RUN1="$TMP_ROOT/run1.txt"
RUN2="$TMP_ROOT/run2.txt"
NORM1="$TMP_ROOT/packet1.norm"
NORM2="$TMP_ROOT/packet2.norm"

rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT"

make_repo() {
  local label="$1"
  local repo="$ROOT/$TMP_ROOT/repo_${label}"
  local remote="$ROOT/$TMP_ROOT/remote_${label}.git"

  git init --bare "$remote" >/dev/null
  git init "$repo" >/dev/null

  (
    cd "$repo"
    git config user.name test
    git config user.email test@example.com

    printf 'root\n' > normal.txt
    mkdir -p system/tests
    cat > system/tests/test_no_conflict_markers_tracked.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
echo "CASE=NO_CONFLICT_MARKERS_TRACKED PASS"
SH
    cat > system/tests/test_no_absolute_paths_tracked.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
echo "CASE=NO_ABSOLUTE_PATHS_TRACKED PASS"
SH
    cat > system/tests/test_no_trailing_whitespace.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
echo "CASE=NO_TRAILING_WHITESPACE PASS"
SH
    chmod +x system/tests/test_no_conflict_markers_tracked.sh \
      system/tests/test_no_absolute_paths_tracked.sh \
      system/tests/test_no_trailing_whitespace.sh
    GIT_AUTHOR_DATE="2000-01-01T00:00:00Z" GIT_COMMITTER_DATE="2000-01-01T00:00:00Z" \
      git add normal.txt system/tests/test_no_conflict_markers_tracked.sh system/tests/test_no_absolute_paths_tracked.sh system/tests/test_no_trailing_whitespace.sh
    GIT_AUTHOR_DATE="2000-01-01T00:00:00Z" GIT_COMMITTER_DATE="2000-01-01T00:00:00Z" \
      git commit -m init >/dev/null

    git branch -M main
    git remote add origin "$remote"
    git push -u origin main >/dev/null

    git checkout -b safe >/dev/null
    printf 'safe\n' >> normal.txt
    GIT_AUTHOR_DATE="2000-01-01T00:00:01Z" GIT_COMMITTER_DATE="2000-01-01T00:00:01Z" \
      git add normal.txt
    GIT_AUTHOR_DATE="2000-01-01T00:00:01Z" GIT_COMMITTER_DATE="2000-01-01T00:00:01Z" \
      git commit -m safe >/dev/null
    git push -u origin safe >/dev/null
    git checkout main >/dev/null
  )

  echo "$repo"
}

run_once() {
  local label="$1"
  local out_file="$2"
  local packet_norm="$3"

  local repo
  repo="$(make_repo "$label")"

  local branches_abs="$ROOT/$TMP_ROOT/branches_${label}.txt"
  printf 'origin/safe\n' > "$branches_abs"

  MERGE_REHEARSAL_REPO="$repo" \
    bash scripts/dev_merge_rehearsal_from_spine.sh --branches-file "$branches_abs" > "$out_file"

  local out_dir packet_name packet_path
  out_dir="$(sed -n 's/^MERGE_REHEARSAL_OUT=//p' "$out_file")"
  packet_name="$(sed -n 's/^MERGE_REHEARSAL_PACKET=//p' "$out_file")"

  [[ -n "$out_dir" ]] || { echo "FAIL:NO_OUT_DIR"; exit 1; }
  [[ -n "$packet_name" ]] || { echo "FAIL:NO_PACKET_NAME"; exit 1; }
  [[ "$out_dir" == out/merge_windows/*/ ]] || { echo "FAIL:OUT_CONTRACT"; exit 1; }

  packet_path="$repo/${out_dir}${packet_name}"
  [[ -f "$packet_path" ]] || { echo "FAIL:PACKET_MISSING"; exit 1; }

  grep -q '^MERGE_WINDOW=' "$packet_path"
  grep -q '^BASE_SHA=' "$packet_path"
  grep -q '^FINAL_SHA=' "$packet_path"
  grep -q '^PUSH_STATUS=SIMULATION_ONLY$' "$packet_path"

  sed -E \
    -e 's#/Users/[^[:space:]]+#<ABS_PATH>#g' \
    -e 's#/tmp/[^[:space:]]+#<TMP_PATH>#g' \
    -e 's#out/test_dev_merge_rehearsal_integration/repo_[^[:space:]]+#<TEMP_REPO>#g' \
    "$packet_path" > "$packet_norm"
}

run_once one "$RUN1" "$NORM1"
run_once two "$RUN2" "$NORM2"

H1="$(shasum -a 256 "$NORM1" | awk '{print $1}')"
H2="$(shasum -a 256 "$NORM2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "CASE=DEV_MERGE_REHEARSAL_INTEGRATION PASS"
