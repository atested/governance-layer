#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP="out/test_dev_progress_spine_run"
SCRIPTS_DIR="$TMP/scripts"
OUT_ROOT="$TMP/out"
RUN1="$TMP/run1.txt"
RUN2="$TMP/run2.txt"

rm -rf "$TMP"
mkdir -p "$SCRIPTS_DIR" "$OUT_ROOT"

cat > "$SCRIPTS_DIR/dev_phase2_regression.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
root="${SPINE_OUT_ROOT:-out}"
mkdir -p "$root/phase2_reports/latest"
cat > "$root/phase2_reports/latest/report.v1.json" <<'JSON'
{"report_version":"phase2_report_v1","base_sha":"UNKNOWN","results":[]}
JSON
SH

cat > "$SCRIPTS_DIR/dev_progress_status.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
root="${SPINE_OUT_ROOT:-out}"
mkdir -p "$root/progress_status/latest"
cat > "$root/progress_status/latest/status.v1.json" <<'JSON'
{"open_verifications":[],"blocked_by_dependencies":[]}
JSON
SH

cat > "$SCRIPTS_DIR/dev_next_actions_compiler.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
root="${SPINE_OUT_ROOT:-out}"
mkdir -p "$root/next_actions/latest"
cat > "$root/next_actions/latest/next_actions.v1.json" <<'JSON'
{"version":"next_actions_v1","open":[]}
JSON
SH

cat > "$SCRIPTS_DIR/dev_merge_sim_inputs_from_queue.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
root="${SPINE_OUT_ROOT:-out}"
mkdir -p "$root/merge_sim_inputs/latest"
printf 'MERGE_SIM_INPUTS_EMPTY=YES\n' > "$root/merge_sim_inputs/latest/branches.txt"
exit 1
SH

chmod +x "$SCRIPTS_DIR"/*.sh

SPINE_SCRIPTS_DIR="$SCRIPTS_DIR" SPINE_OUT_ROOT="$OUT_ROOT" bash scripts/dev_progress_spine_run.sh > "$RUN1"
SPINE_SCRIPTS_DIR="$SCRIPTS_DIR" SPINE_OUT_ROOT="$OUT_ROOT" bash scripts/dev_progress_spine_run.sh > "$RUN2"

H1="$(shasum -a 256 "$RUN1" | awk '{print $1}')"
H2="$(shasum -a 256 "$RUN2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

grep -qx 'SPINE_RUN=PASS' "$RUN1"
grep -qx "REPORT_PHASE2=$OUT_ROOT/phase2_reports/latest/report.v1.json" "$RUN1"
grep -qx "REPORT_STATUS=$OUT_ROOT/progress_status/latest/status.v1.json" "$RUN1"
grep -qx "REPORT_NEXT_ACTIONS=$OUT_ROOT/next_actions/latest/next_actions.v1.json" "$RUN1"
grep -qx 'MERGE_SIM_BRANCHES=EMPTY' "$RUN1"

echo "CASE=DEV_PROGRESS_SPINE_RUN PASS"
