#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SUMMARY_JSON_PATH="${VALIDATE_PROOF_BUNDLE_SUMMARY_JSON:-}"
SUMMARY_RESULT=""
SUMMARY_EXIT_CODE=""
SUMMARY_REASON=""
AAT_SHIM_ENABLE="${AAT_SHIM_ENABLE:-0}"
AAT_SHIM_STRICT="${AAT_SHIM_STRICT:-0}"
AAT_SHIM_LEDGER_PATH="${AAT_SHIM_LEDGER_PATH:-}"

summary_bundle_basename() { [[ -n "${bundle_dir:-}" ]] && basename "$bundle_dir" || echo ""; }

write_summary_json() {
  [[ -n "$SUMMARY_JSON_PATH" ]] || return 0
  python3 - <<'PY' \
    "$SUMMARY_JSON_PATH" \
    "${SUMMARY_RESULT:-}" \
    "${SUMMARY_EXIT_CODE:-}" \
    "${bundle_dir:-}" \
    "${actual_packet_sha:-}" \
    "${proof_packet_summary_sha:-}" \
    "${qds_status:-unknown}" \
    "${status_bundle_state:-unknown}" \
    "${queue_drift_scan_json_present:-false}" \
    "${status_bundle_json_present:-false}" \
    "${SUMMARY_REASON:-}"
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
result = sys.argv[2] or "ERROR"
try:
    exit_code = int(sys.argv[3])
except ValueError:
    exit_code = 2
bundle_dir = sys.argv[4]
packet_sha = sys.argv[5]
summary_sha = sys.argv[6]
qds_status = sys.argv[7] or "unknown"
status_bundle_status = sys.argv[8] or "unknown"
qds_json_present = sys.argv[9].lower() == "true"
status_json_present = sys.argv[10].lower() == "true"
reason = sys.argv[11]
payload = {
    "bundle_dir_basename": Path(bundle_dir).name if bundle_dir else "",
    "counts": {"extra": 0, "fatal": 0, "missing": 0, "mismatched": 0},
    "exit_code": exit_code,
    "packet_hash": {"algo": "sha256", "value": packet_sha or ""},
    "proof_packet_version": "proof_packet_v1",
    "queue_drift_scan": {"status": qds_status},
    "queue_drift_scan_json_present": qds_json_present,
    "report_version": "validate_proof_bundle_summary_v1",
    "result": result,
    "status_bundle": {"status": status_bundle_status},
    "status_bundle_present": status_json_present,
    "summary_hash": {"algo": "sha256", "value": summary_sha or ""},
}
if result == "FAIL":
    payload["contract_failures"] = [reason] if reason else []
elif result == "ERROR":
    payload["runtime_error"] = reason or "runtime error"
if bundle_dir:
    try:
        vsum_path = Path(bundle_dir) / "proof_packet_verify_summary.json"
        vsum = json.loads(vsum_path.read_text(encoding="utf-8"))
        gov_ev = vsum.get("governance_evidence")
        if isinstance(gov_ev, dict):
            replay_outcome = gov_ev.get("replay_outcome")
            if replay_outcome not in ("pass", "fail", "unavailable"):
                gov_ev = dict(gov_ev)
                gov_ev["replay_outcome"] = "unavailable"
            payload["governance_evidence"] = gov_ev
    except Exception:
        pass
out.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

fail_contract() {
  SUMMARY_RESULT="FAIL"
  SUMMARY_EXIT_CODE="1"
  SUMMARY_REASON="$1"
  write_summary_json
  echo "FAIL: $1"
  exit 1
}

runtime_error() {
  SUMMARY_RESULT="ERROR"
  SUMMARY_EXIT_CODE="2"
  SUMMARY_REASON="$1"
  write_summary_json
  echo "ERROR: $1" >&2
  exit 2
}

run_aat_shim() {
  [[ "$AAT_SHIM_ENABLE" == "1" ]] || return 0

  case "$AAT_SHIM_STRICT" in
    0|1) ;;
    *) runtime_error "AAT_SHIM_STRICT must be 0 or 1" ;;
  esac

  discover_aat_inputs() {
    local root="$1"
    local action_rel=""
    local decision_rel=""

    # Deterministic legacy+preferred lookup order:
    # 1) root
    # 2) aat/
    # 3) evidence/aat/
    local candidates=(
      "."
      "aat"
      "evidence/aat"
    )
    local rel
    for rel in "${candidates[@]}"; do
      local a d
      if [[ "$rel" == "." ]]; then
        a="$root/action_record.json"
        d="$root/decision_record.json"
      else
        a="$root/$rel/action_record.json"
        d="$root/$rel/decision_record.json"
      fi
      if [[ -f "$a" && -f "$d" ]]; then
        action_rel="$a"
        decision_rel="$d"
        if [[ "$rel" == "." ]]; then
          echo "AAT_SHIM_INPUTS=FOUND path=."
        else
          echo "AAT_SHIM_INPUTS=FOUND path=$rel"
        fi
        ACTION_RECORD="$action_rel"
        DECISION_RECORD="$decision_rel"
        return 0
      fi
    done

    echo "AAT_SHIM_INPUTS=MISSING"
    return 1
  }

  ACTION_RECORD=""
  DECISION_RECORD=""
  discover_aat_inputs "$bundle_dir" || true
  action_record="$ACTION_RECORD"
  decision_record="$DECISION_RECORD"

  if [[ -z "$action_record" || -z "$decision_record" ]]; then
    if [[ "$AAT_SHIM_STRICT" == "1" ]]; then
      echo "AAT_SHIM_RESULT=NON_ADMISSIBLE REASON_CODE=AAT_SHIM_INPUTS_MISSING LEDGER_APPENDED=NO"
      fail_contract "AAT_SHIM_INPUTS_MISSING"
    fi
    echo "AAT_SHIM=SKIP INPUTS_MISSING"
    return 0
  fi

  ledger_path="$AAT_SHIM_LEDGER_PATH"
  if [[ -z "$ledger_path" ]]; then
    ledger_path="$bundle_dir/aat_gate_c_ledger.jsonl"
  fi

  shim_out="$("$ROOT/system/scripts/aat-gate-c-wrapper.sh" \
    --action-record "$action_record" \
    --decision-record "$decision_record" \
    --ledger "$ledger_path" 2>&1 || true)"

  shim_norm="$(printf '%s\n' "$shim_out" | "$ROOT/system/scripts/aat-gate-c-normalize.sh")"
  shim_status="$(printf '%s\n' "$shim_norm" | rg -m1 '^STATUS=' | cut -d= -f2- || true)"
  shim_reason="$(printf '%s\n' "$shim_norm" | rg -m1 '^REASON_CODE=' | cut -d= -f2- || true)"
  shim_appended="$(printf '%s\n' "$shim_norm" | rg -m1 '^LEDGER_APPENDED=' | cut -d= -f2- || true)"
  shim_status="${shim_status:-HARD_STOP}"
  shim_reason="${shim_reason:-AAT_SHIM_UNKNOWN}"
  shim_appended="${shim_appended:-NO}"

  echo "AAT_SHIM_RESULT=$shim_status REASON_CODE=$shim_reason LEDGER_APPENDED=$shim_appended"

  if [[ "$shim_status" == "HARD_STOP" ]]; then
    shim_inputs_subreason="AAT_INPUTS_UNKNOWN"
    case "$shim_reason" in
      *BINDING*) shim_inputs_subreason="AAT_INPUTS_BINDING_MISMATCH" ;;
      *SCHEMA*) shim_inputs_subreason="AAT_INPUTS_SCHEMA_INVALID" ;;
      *JSON*) shim_inputs_subreason="AAT_INPUTS_JSON_INVALID" ;;
      *LAYOUT*|*AMBIG*) shim_inputs_subreason="AAT_INPUTS_LAYOUT_AMBIGUOUS" ;;
      *MISSING*|*NOT_FOUND*) shim_inputs_subreason="AAT_INPUTS_MISSING_FILE" ;;
    esac
    echo "AAT_INPUTS_SUBREASON=$shim_inputs_subreason"
    fail_contract "AAT_SHIM_HARD_STOP:$shim_reason"
  fi
  if [[ "$shim_status" == "NON_ADMISSIBLE" && "$AAT_SHIM_STRICT" == "1" ]]; then
    fail_contract "AAT_SHIM_NON_ADMISSIBLE:$shim_reason"
  fi
}

bundle_dir=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --summary-json)
      SUMMARY_JSON_PATH="$2"; shift 2 ;;
    -h|--help)
      cat <<'EOF'
Usage: system/scripts/validate-proof-bundle.sh [BUNDLE_DIR] [--summary-json PATH]
EOF
      exit 0 ;;
    --*)
      runtime_error "unknown arg: $1" ;;
    *)
      if [[ -n "$bundle_dir" ]]; then
        runtime_error "multiple bundle dirs provided"
      fi
      bundle_dir="$1"; shift ;;
  esac
done

if [[ -z "$bundle_dir" ]]; then
  base="$ROOT/out/proof-bundles"
  [[ -d "$base" ]] || fail_contract "proof-bundle base missing: $base"
  bundle_dir="$(find "$base" -mindepth 1 -maxdepth 1 -type d | LC_ALL=C sort | tail -n 1)"
  [[ -n "$bundle_dir" ]] || fail_contract "no proof-bundle directories found under $base"
fi

[[ -d "$bundle_dir" ]] || fail_contract "bundle directory not found: $bundle_dir"

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

validate_kv_file() {
  python3 - <<'PY' "$1" "$2"
import sys
from pathlib import Path
p = Path(sys.argv[1]); label = sys.argv[2]
seen = set()
for i, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
    if "=" not in raw:
        print(f"FAIL:{label}:line{ i }:missing_equals")
        raise SystemExit(1)
    if " = " in raw or raw.startswith(" ") or raw.endswith(" "):
        print(f"FAIL:{label}:line{ i }:spaces_around_equals")
        raise SystemExit(1)
    k, v = raw.split("=", 1)
    if not k:
        print(f"FAIL:{label}:line{ i }:empty_key")
        raise SystemExit(1)
    if k in seen:
        print(f"FAIL:{label}:line{ i }:duplicate_key:{k}")
        raise SystemExit(1)
    seen.add(k)
print(f"PASS:{label}:kv_contract")
print(f"COUNT:{label}={len(seen)}")
PY
}

required=(
  "proof_packet.tar"
  "proof_packet.sha256"
  "proof_packet_verify_summary.json"
  "release_gate_log.txt"
  "versions.txt"
)

for f in "${required[@]}"; do
  [[ -f "$bundle_dir/$f" ]] || fail_contract "missing required file: $f"
done

sha_line="$(cat "$bundle_dir/proof_packet.sha256")"
if [[ ! "$sha_line" =~ ^([0-9a-f]{64})[[:space:]]{2}proof_packet\.tar$ ]]; then
  fail_contract "proof_packet.sha256 format invalid"
fi
declared_packet_sha="${BASH_REMATCH[1]}"
actual_packet_sha="$(sha256_file "$bundle_dir/proof_packet.tar")"
[[ "$declared_packet_sha" == "$actual_packet_sha" ]] || fail_contract "proof_packet.sha256 mismatch"

summary_checks="$(python3 - <<'PY' "$bundle_dir/proof_packet_verify_summary.json"
import json, sys
from pathlib import Path
j = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
rv = j.get("report_version")
if rv != "proof_packet_verify_summary_v1":
    print("FAIL:summary report_version mismatch")
    raise SystemExit(1)
print(f"SUMMARY_REPORT_VERSION={rv}")
print(f"SUMMARY_RESULT={j.get('result')}")
PY
)" || { printf '%s\n' "$summary_checks"; exit 1; }

manifest_checks="$(python3 - <<'PY' "$bundle_dir/proof_packet.tar"
import io, json, tarfile, sys
from pathlib import Path
tar_path = Path(sys.argv[1])
with tarfile.open(tar_path, "r") as tf:
    names = tf.getnames()
    if "manifest.json" not in names:
        print("FAIL: missing manifest.json")
        raise SystemExit(1)
    manifest_bytes = tf.extractfile("manifest.json").read()
    m = json.loads(manifest_bytes.decode("utf-8"))
    pv = m.get("proof_packet_version")
    if pv != "proof_packet_v1":
        print("FAIL: manifest proof_packet_version mismatch")
        raise SystemExit(1)
    files = m.get("files")
    if not isinstance(files, dict):
        print("FAIL: manifest files not object")
        raise SystemExit(1)
    if "record.json" not in files:
        print("FAIL: manifest missing record.json")
        raise SystemExit(1)
print(f"MANIFEST_PROOF_PACKET_VERSION={pv}")
print(f"MANIFEST_FILE_COUNT={len(files)}")
PY
)" || { printf '%s\n' "$manifest_checks"; exit 1; }

kv_versions="$(validate_kv_file "$bundle_dir/versions.txt" "versions.txt")" || { printf '%s\n' "$kv_versions"; exit 1; }
kv_log="$(validate_kv_file "$bundle_dir/release_gate_log.txt" "release_gate_log.txt")" || { printf '%s\n' "$kv_log"; exit 1; }

qds_status="absent"
if [[ -f "$bundle_dir/queue_drift_scan.txt" ]]; then
  qds_status="present"
  qds_text="$(cat "$bundle_dir/queue_drift_scan.txt")"
  if [[ -z "$qds_text" ]]; then
    fail_contract "queue_drift_scan.txt empty"
  fi
  if [[ "$qds_text" == INFO:\ queue-drift-scan\ unavailable* ]]; then
    echo "QUEUE_DRIFT_SCAN_SEMANTICS=sentinel"
  else
    echo "QUEUE_DRIFT_SCAN_SEMANTICS=human_text"
  fi

  if [[ -f "$bundle_dir/queue_drift_scan.json" ]]; then
    qds_json_checks="$(python3 - <<'PY' "$bundle_dir/queue_drift_scan.json" "$bundle_dir/queue_drift_scan.txt"
import hashlib, json, sys
from pathlib import Path
j = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
txt_bytes = Path(sys.argv[2]).read_bytes()
if j.get("queue_drift_scan_version") != "queue_drift_scan_v1":
    print("FAIL: queue_drift_scan.json version mismatch")
    raise SystemExit(1)
rc = j.get("rc")
if not isinstance(rc, int):
    print("FAIL: queue_drift_scan.json rc not int")
    raise SystemExit(1)
status = j.get("status")
if status not in ("present", "unavailable"):
    print("FAIL: queue_drift_scan.json status invalid")
    raise SystemExit(1)
digest = hashlib.sha256(txt_bytes).hexdigest()
if j.get("text_sha256") != digest:
    print("FAIL: queue_drift_scan.json text_sha256 linkage mismatch")
    raise SystemExit(1)
print("QUEUE_DRIFT_SCAN_JSON_VERSION=queue_drift_scan_v1")
print(f"QUEUE_DRIFT_SCAN_JSON_STATUS={status}")
print("PASS: queue_drift_scan.json schema/version and text digest linkage valid")
PY
)" || { printf '%s\n' "$qds_json_checks"; exit 1; }
    printf '%s\n' "$qds_json_checks"
  else
    echo "INFO: queue_drift_scan.json absent (optional)"
  fi
else
  if [[ -f "$bundle_dir/queue_drift_scan.json" ]]; then
    fail_contract "queue_drift_scan.json present without queue_drift_scan.txt"
  fi
  echo "INFO: queue_drift_scan.json absent (optional)"
  echo "QUEUE_DRIFT_SCAN_SEMANTICS=absent"
fi

status_bundle_state="absent"
queue_drift_scan_json_present="false"
status_bundle_json_present="false"
if [[ -f "$bundle_dir/status_bundle.json" ]]; then
  status_bundle_state="present"
  status_bundle_json_present="true"
  status_checks="$(python3 - <<'PY' "$bundle_dir/status_bundle.json"
import json, sys
from pathlib import Path
j = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if j.get("status_bundle_version") != "status_bundle_v1":
    print("FAIL: status_bundle_version mismatch")
    raise SystemExit(1)
strict = j.get("strictness", {})
if not isinstance(strict, dict):
    print("FAIL: strictness not object")
    raise SystemExit(1)
value = strict.get("value")
if not isinstance(value, int) or value not in (0, 1):
    print("FAIL: strictness.value not int 0|1")
    raise SystemExit(1)
for key in ("repo_git_sha", "gov_profile", "release_gate_result", "proof_packet_sha256", "proof_packet_verify_summary_sha256", "queue_drift_scan"):
    if key not in j:
        print(f"FAIL: missing status_bundle key {key}")
        raise SystemExit(1)
print("STATUS_BUNDLE_VERSION=status_bundle_v1")
print(f"STATUS_BUNDLE_STRICTNESS_VALUE={value}")
PY
)" || { printf '%s\n' "$status_checks"; exit 1; }
  printf '%s\n' "$status_checks"
else
  echo "STATUS_BUNDLE_VERSION=absent"
fi

if [[ -f "$bundle_dir/queue_drift_scan.json" ]]; then
  queue_drift_scan_json_present="true"
fi

printf '%s\n' "$summary_checks"
printf '%s\n' "$manifest_checks"
printf '%s\n' "$kv_versions"
printf '%s\n' "$kv_log"
echo "BUNDLE_DIR=$bundle_dir"
echo "PROOF_PACKET_SHA256=$actual_packet_sha"
proof_packet_summary_sha="$(sha256_file "$bundle_dir/proof_packet_verify_summary.json")"
echo "PROOF_PACKET_VERIFY_SUMMARY_SHA256=$proof_packet_summary_sha"
echo "QUEUE_DRIFT_SCAN_STATUS=$qds_status"
echo "STATUS_BUNDLE_STATUS=$status_bundle_state"
run_aat_shim
echo "PASS: proof-bundle external contract valid"

if [[ -n "$SUMMARY_JSON_PATH" ]]; then
  SUMMARY_RESULT="PASS"
  SUMMARY_EXIT_CODE="0"
  SUMMARY_REASON=""
  write_summary_json
  echo "SUMMARY_JSON_PATH=$SUMMARY_JSON_PATH"
fi
