#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
usage: scripts/dev_phase2_regression.sh [--catalog <path>] [--report <path>]
Runs deterministic Phase2 checks and emits machine report JSON.
USAGE
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CATALOG_PATH="$ROOT/system/planning/verification_catalog.v1.json"
REPORT_PATH="$ROOT/out/phase2_reports/latest/report.v1.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --catalog)
      [[ $# -ge 2 ]] || { echo "FAIL: --catalog requires path"; usage; exit 2; }
      CATALOG_PATH="$2"
      shift 2
      ;;
    --report)
      [[ $# -ge 2 ]] || { echo "FAIL: --report requires path"; usage; exit 2; }
      REPORT_PATH="$2"
      shift 2
      ;;
    *)
      echo "FAIL: unknown arg: $1"
      usage
      exit 2
      ;;
  esac
done

mkdir -p "$(dirname "$REPORT_PATH")"
TMP_RESULTS="$(mktemp "${TMPDIR:-/tmp}/phase2-results.XXXXXX")"
trap 'rm -f "$TMP_RESULTS"' EXIT

SURFACES=(
  "bash system/tests/test_phase2_obj2_registry_source_parity.sh"
  "bash system/tests/test_phase2_obj3_reason_precedence_dedup.sh"
  "bash system/tests/test_phase2_one_command_regression.sh"
  "bash system/tests/test_phase2_merge_prep_queue_helper.sh"
  "bash system/tests/test_progress_map_canon_generation.sh"
  "bash system/tests/test_verify_attestation_bundle_signature_mode.sh"
  "bash system/tests/test_attestation_sign_verify_e2e.sh"
  "bash system/tests/test_ed25519_attestation_primitives.sh"
  "bash system/tests/test_mcp_capabilities_execute_fs_move.sh"
  "bash system/tests/test_mcp_capabilities_execute_blocked.sh"
  "bash system/tests/test_mcp_capabilities_execute_delete_exec.sh"
  "bash system/tests/test_mcp_capabilities_execute_fs_copy.sh"
  "bash system/tests/test_mcp_capabilities_execute_delete_nonexec.sh"
  "bash system/tests/test_mcp_receipt_store_index.sh"
  "bash system/tests/test_mcp_receipt_and_list_recent.sh"
  "bash system/tests/test_mcp_replay_check.sh"
  "bash system/tests/test_mcp_replay_check_emits_artifact.sh"
  "bash system/tests/test_export_receipt_bundle_includes_replay_check.sh"
  "bash system/tests/test_verify_receipt_bundle_replay_check_artifact.sh"
  "bash system/tests/test_mcp_admissibility_policy_context_drift.sh"
  "bash system/tests/test_mcp_replay_check_policy_context_drift.sh"
  "bash system/tests/test_mcp_receipt_signature_primitives.sh"
  "bash system/tests/test_mcp_receipt_signature_verification.sh"
  "bash system/tests/test_export_receipt_attestation_bundle.sh"
  "bash system/tests/test_verify_receipt_attestation_bundle.sh"
  "bash system/tests/test_mcp_export_receipt_attestation.sh"
  "bash system/tests/test_export_receipt_bundle_signature_parity.sh"
  "bash system/tests/test_verify_receipt_bundle_require_signature.sh"
  "bash system/tests/test_mcp_attested_execute_fs_move.sh"
  "bash system/tests/test_mcp_attested_execute_fail_closed.sh"
  "bash system/tests/test_mcp_attested_execute_includes_replay_artifact.sh"
  "bash system/tests/test_mcp_attested_execute_replay_context_unknown.sh"
  "bash system/tests/test_mcp_reference_workflow_e2e.sh"
  "bash system/tests/test_mcp_noop_echo_capability.sh"
  "bash system/tests/test_mcp_ingest_artifact_attested_small_payload.sh"
  "bash system/tests/test_mcp_ingest_artifact_rejects_large_payload.sh"
  "bash system/tests/test_mcp_ingest_tool_event_attested_ok.sh"
  "bash system/tests/test_mcp_ingest_tool_event_rejects_invalid.sh"
  "bash system/tests/test_mcp_tool_catalog_register_and_get.sh"
  "bash system/tests/test_mcp_tool_catalog_list_recent.sh"
  "bash system/tests/test_export_tool_catalog_bundle.sh"
  "bash system/tests/test_verify_tool_catalog_bundle.sh"
  "bash system/tests/test_mcp_tool_catalog_export_bundle.sh"
  "bash system/tests/test_mcp_tool_catalog_verify_bundle.sh"
  "bash system/tests/test_p4_fs_delete_nonexec_admissibility.sh"
  "bash system/tests/test_p4_fs_copy_admissibility.sh"
  "bash system/tests/test_p4_fs_move_dir_semantics.sh"
)

resolve_id() {
  local cmd="$1"
  python3 - "$CATALOG_PATH" "$cmd" <<'PY'
import hashlib
import json
import pathlib
import re
import sys

catalog = pathlib.Path(sys.argv[1])
cmd = sys.argv[2]
if catalog.is_file():
    data = json.loads(catalog.read_text(encoding='utf-8'))
    for e in data.get('entries', []):
        if e.get('verification_cmd') == cmd:
            print(e.get('id'))
            raise SystemExit(0)
slug = re.sub(r'[^a-z0-9]+', '_', cmd.lower()).strip('_') or 'entry'
digest = hashlib.sha256(cmd.encode('utf-8')).hexdigest()[:8]
print(f"VCAT_{slug}_{digest}")
PY
}

append_result() {
  local id="$1" status="$2" cmd="$3" rc="$4" skip_reason="$5"
  printf '%s\t%s\t%s\t%s\t%s\n' "$id" "$status" "$cmd" "$rc" "$skip_reason" >> "$TMP_RESULTS"
}

run_surface() {
  local cmd="$1"
  local id
  id="$(resolve_id "$cmd")"
  if [[ "$cmd" == bash* ]]; then
    local script_path="${cmd#bash }"
    if [[ ! -f "$ROOT/$script_path" ]]; then
      append_result "$id" "SKIP" "$cmd" "127" "MISSING_COMMAND"
      return
    fi
  fi
  set +e
  (cd "$ROOT" && eval "$cmd") >/dev/null 2>&1
  local rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    append_result "$id" "PASS" "$cmd" "$rc" ""
  else
    append_result "$id" "FAIL" "$cmd" "$rc" ""
  fi
}

for cmd in "${SURFACES[@]}"; do
  run_surface "$cmd"
done

python3 - "$TMP_RESULTS" "$REPORT_PATH" <<'PY'
import json
import pathlib
import sys

rows = []
for line in pathlib.Path(sys.argv[1]).read_text(encoding='utf-8').splitlines():
    id_, status, cmd, rc, skip_reason = line.split('\t')
    rows.append({
        "id": id_,
        "status": status,
        "cmd": cmd,
        "rc": int(rc),
        "skip_reason": skip_reason,
    })
rows.sort(key=lambda x: x['id'])
out = {
    "report_version": "phase2_report_v1",
    "base_sha": "UNKNOWN",
    "results": rows,
}
path = pathlib.Path(sys.argv[2])
path.write_text(json.dumps(out, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
print(f"REPORT_ROWS={len(rows)}")
print(f"REPORT_PATH={path}")
PY

cat "$REPORT_PATH"
