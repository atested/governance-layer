#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STRICT_PROOF_PACKET="${RELEASE_GATE_STRICT_PROOF_PACKET:-}"
GOV_PROFILE="${GOV_PROFILE:-dev}"
STRICT_PROOF_PACKET_SOURCE=""
SKIP_BASE="${RELEASE_GATE_SKIP_BASE:-0}"
PROOF_BUNDLE_OUT_BASE="${RELEASE_GATE_PROOF_BUNDLE_OUT_BASE:-$ROOT/out/proof-bundles}"
RUN_ID="${RELEASE_GATE_RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
TOOL_EVENTS_FILE="$(mktemp "${TMPDIR:-/tmp}/release-gate-tool-events.XXXXXX")"

cleanup_tool_events(){
  rm -f "$TOOL_EVENTS_FILE"
}
trap cleanup_tool_events EXIT

resolve_proof_packet_strictness(){
  if [[ -n "${RELEASE_GATE_STRICT_PROOF_PACKET:-}" ]]; then
    STRICT_PROOF_PACKET="$RELEASE_GATE_STRICT_PROOF_PACKET"
    STRICT_PROOF_PACKET_SOURCE="env_override"
    echo "INFO: proof-packet strictness source=env_override value=$STRICT_PROOF_PACKET"
    return 0
  fi
  case "$GOV_PROFILE" in
    dev) STRICT_PROOF_PACKET=0 ;;
    ci) STRICT_PROOF_PACKET=1 ;;
    *) echo "ERROR: unsupported GOV_PROFILE=$GOV_PROFILE" >&2; exit 2 ;;
  esac
  STRICT_PROOF_PACKET_SOURCE="profile"
  echo "INFO: proof-packet strictness source=profile GOV_PROFILE=$GOV_PROFILE value=$STRICT_PROOF_PACKET"
}

run_cmd(){
  echo "$ $*"
  local tmpdir stdout_file stderr_file
  tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/release-gate-run-cmd.XXXXXX")"
  stdout_file="$tmpdir/stdout"
  stderr_file="$tmpdir/stderr"
  set +e
  "$@" >"$stdout_file" 2>"$stderr_file"
  local rc=$?
  set -e
  cat "$stdout_file"
  cat "$stderr_file" >&2
  record_tool_event "$rc" "$stdout_file" "$stderr_file" "$@"
  rm -rf "$tmpdir"
  echo "[exit=$rc]"
  if [[ $rc -ne 0 ]]; then
    exit $rc
  fi
}

sha256_file(){
  local p="$1"
  echo "sha256:$(shasum -a 256 "$p" | awk '{print $1}')"
}

normalize_argv_norm(){
  python3 - <<'PY' "$ROOT" "$@"
import os
import re
import sys
from pathlib import Path

root = os.path.abspath(sys.argv[1])
argv = sys.argv[2:]

def norm(tok: str) -> str:
    if tok.startswith(root + os.sep):
        tok = tok[len(root) + 1 :]
    tok = re.sub(r"/tmp/\S+", "<TMP>", tok)
    tok = re.sub(r"/var/folders/\S+", "<TMP>", tok)
    tok = " ".join(tok.split())
    return tok

normed = [norm(a) for a in argv]
print("\x1f".join(normed))
PY
}

sha256_text_file_normalized(){
  python3 - <<'PY' "$1" "$ROOT"
import hashlib
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
root = sys.argv[2]
txt = p.read_text(encoding="utf-8", errors="ignore")
txt = txt.replace(root + "/", "")
txt = txt.replace(root, "<ROOT>")
txt = re.sub(r"/tmp/\S+", "<TMP>", txt)
txt = re.sub(r"/var/folders/\S+", "<TMP>", txt)
print("sha256:" + hashlib.sha256(txt.encode("utf-8")).hexdigest())
PY
}

emit_tool_event_line(){
  python3 - <<'PY' "$@"
import json
import sys
from pathlib import Path

tool = Path(sys.argv[1]).name
argv_norm = sys.argv[2]
rc = int(sys.argv[3])
stdout_sha = sys.argv[4]
stderr_sha = sys.argv[5]
doc = {
    "tool_event_version": "v0",
    "tool": tool,
    "argv_norm": argv_norm,
    "rc": rc,
    "stdout_sha256": stdout_sha,
    "stderr_sha256": stderr_sha,
}
print(json.dumps(doc, sort_keys=True, separators=(",", ":")))
PY
}

record_tool_event(){
  local rc="$1" stdout_file="$2" stderr_file="$3"; shift 3
  local stdout_sha stderr_sha argv_norm line
  stdout_sha="$(sha256_text_file_normalized "$stdout_file")"
  stderr_sha="$(sha256_text_file_normalized "$stderr_file")"
  argv_norm="$(normalize_argv_norm "$@")"
  line="$(emit_tool_event_line "$1" "$argv_norm" "$rc" "$stdout_sha" "$stderr_sha")"
  printf '%s\n' "$line" >> "$TOOL_EVENTS_FILE"
}

run_capture_cmd(){
  local __stdout_var="$1" __stderr_var="$2"; shift 2
  local tmpdir stdout_file stderr_file out err rc
  tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/release-gate-capture-cmd.XXXXXX")"
  stdout_file="$tmpdir/stdout"
  stderr_file="$tmpdir/stderr"
  set +e
  "$@" >"$stdout_file" 2>"$stderr_file"
  rc=$?
  set -e
  out="$(cat "$stdout_file")"
  err="$(cat "$stderr_file")"
  printf -v "$__stdout_var" '%s' "$out"
  printf -v "$__stderr_var" '%s' "$err"
  record_tool_event "$rc" "$stdout_file" "$stderr_file" "$@"
  rm -rf "$tmpdir"
  return "$rc"
}

emit_kv_file_canonical(){
  local out="$1"; shift
  python3 - <<'PY' "$out" "$@"
import sys
from pathlib import Path
out = Path(sys.argv[1])
pairs = []
seen = set()
for raw in sys.argv[2:]:
    if "=" not in raw:
        raise SystemExit(f"invalid kv pair: {raw}")
    k, v = raw.split("=", 1)
    if not k:
        raise SystemExit("empty key")
    if k in seen:
        raise SystemExit(f"duplicate key: {k}")
    seen.add(k)
    pairs.append((k, v))
pairs.sort(key=lambda kv: kv[0])
out.write_text("".join(f"{k}={v}\n" for k, v in pairs), encoding="utf-8")
PY
}

run_ci_contract_checks(){
  if [[ "${RELEASE_GATE_SKIP_CI_CONTRACT_SUITE:-0}" == "1" ]]; then
    echo "INFO: ci contract suite skipped via RELEASE_GATE_SKIP_CI_CONTRACT_SUITE=1"
    return 0
  fi
  if [[ "$GOV_PROFILE" != "ci" ]]; then
    return 0
  fi
  echo "## External CI Contract Checks (GOV_PROFILE=ci)"
  run_cmd env GOV_PROFILE=dev RELEASE_GATE_SKIP_CI_CONTRACT_SUITE=1 bash tests/test_proof_packet_contract_enforcement.sh
  run_cmd env GOV_PROFILE=dev RELEASE_GATE_SKIP_CI_CONTRACT_SUITE=1 bash tests/test_release_gate_aux_file_formats.sh
  run_cmd env GOV_PROFILE=dev RELEASE_GATE_SKIP_CI_CONTRACT_SUITE=1 bash tests/test_proof_bundle_contract_required_files.sh
}

run_ci_external_validator(){
  if [[ "$GOV_PROFILE" != "ci" ]]; then
    return 0
  fi
  local outdir="$PROOF_BUNDLE_OUT_BASE/$RUN_ID"
  echo "## External CI Proof-Bundle Validation (GOV_PROFILE=ci)"
  run_cmd bash system/scripts/validate-proof-bundle.sh "$outdir"
  echo "INFO: external proof-bundle validator pass"
}

proof_packet_check(){
  local strict="$STRICT_PROOF_PACKET"
  local fixture_root="${RELEASE_GATE_PROOF_PACKET_FIXTURE_ROOT:-$ROOT/tests/fixtures/attestation_bundle/sample}"
  local packer="$ROOT/scripts/proof-packet.py"
  local workdir
  workdir="$(mktemp -d "${TMPDIR:-/tmp}/release-gate-proof-packet.XXXXXX")"
  trap 'rm -rf "$workdir"' RETURN

  echo "## Proof-Packet Check (informational)"
  echo "INFO: proof-packet strict=${strict}"

  if [[ ! -f "$packer" ]]; then
    if [[ "$strict" == "1" ]]; then
      echo "FAIL: proof-packet check required but unavailable reason=missing_packer path=$packer"
      return 1
    fi
    echo "INFO: proof-packet check skipped reason=missing_packer path=$packer"
    return 0
  fi

  local record="$fixture_root/record.json"
  local artifacts="$fixture_root/artifacts"
  local replay_report="$fixture_root/replay_audit_report.json"
  if [[ ! -f "$record" || ! -d "$artifacts" || ! -f "$replay_report" ]]; then
    if [[ "$strict" == "1" ]]; then
      echo "FAIL: proof-packet check required but unavailable reason=missing_fixture fixture_root=$fixture_root"
      return 1
    fi
    echo "INFO: proof-packet check skipped reason=missing_fixture fixture_root=$fixture_root"
    return 0
  fi

  local packet="$workdir/sample.proof_packet.tar"
  local summary="$workdir/summary.json"
  local pack_out pack_err verify_out verify_err pack_rc verify_rc

  if run_capture_cmd pack_out pack_err python3 "$packer" pack --record "$record" --artifacts-dir "$artifacts" --replay-audit-report "$replay_report" --out "$packet"; then
    pack_rc=0
  else
    pack_rc=$?
  fi
  if [[ -n "$pack_err" ]]; then
    pack_out+=$'\n'"$pack_err"
  fi
  if [[ "$pack_rc" -ne 0 ]]; then
    printf '%s\n' "$pack_out"
    if [[ "$strict" == "1" ]]; then
      echo "FAIL: proof-packet check required but pack failed rc=$pack_rc"
      return 1
    fi
    echo "INFO: proof-packet check non-gating failure stage=pack rc=$pack_rc"
    return 0
  fi

  if run_capture_cmd verify_out verify_err python3 "$packer" verify --bundle "$packet" --summary-json "$summary"; then
    verify_rc=0
  else
    verify_rc=$?
  fi
  if [[ -n "$verify_err" ]]; then
    verify_out+=$'\n'"$verify_err"
  fi
  if [[ "$verify_rc" -ne 0 ]]; then
    printf '%s\n' "$verify_out"
    if [[ "$strict" == "1" ]]; then
      echo "FAIL: proof-packet check required but verify failed rc=$verify_rc"
      return 1
    fi
    echo "INFO: proof-packet check non-gating failure stage=verify rc=$verify_rc"
    return 0
  fi

  local packet_sha summary_sha
  packet_sha="$(python3 - <<'PY' "$packet"
import hashlib,sys
print("sha256:"+hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
)"
  summary_sha="$(python3 - <<'PY' "$summary"
import hashlib,sys
print("sha256:"+hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
)"

  printf '%s\n' "$verify_out"
  emit_proof_bundle_output "$packet" "$summary" "$packet_sha" "$summary_sha"
  echo "INFO: proof-packet check pass packet_sha=${packet_sha} summary_sha=${summary_sha}"
}

emit_proof_bundle_output(){
  local packet="$1" summary="$2" packet_sha="$3" summary_sha="$4"
  local outdir="$PROOF_BUNDLE_OUT_BASE/$RUN_ID"
  mkdir -p "$outdir"
  cp "$packet" "$outdir/proof_packet.tar"
  cp "$summary" "$outdir/proof_packet_verify_summary.json"
  emit_tool_events_jsonl "$outdir"
  emit_input_manifest_json "$outdir"
  printf '%s  %s\n' "${packet_sha#sha256:}" "proof_packet.tar" > "$outdir/proof_packet.sha256"
  emit_kv_file_canonical "$outdir/release_gate_log.txt" \
    "release_gate_proof_packet=pass" \
    "packet_sha=$packet_sha" \
    "strict=$STRICT_PROOF_PACKET" \
    "summary_sha=$summary_sha"
  if command -v python3 >/dev/null 2>&1 && [[ -f "$ROOT/system/scripts/queue-drift-scan.py" ]]; then
    local qds_rc=0
    if python3 "$ROOT/system/scripts/queue-drift-scan.py" > "$outdir/queue_drift_scan.txt" 2>&1; then
      :
    else
      qds_rc=$?
      printf 'INFO: queue-drift-scan nonzero (captured)\n' >> "$outdir/queue_drift_scan.txt"
    fi
    emit_queue_drift_scan_json "$outdir/queue_drift_scan.txt" "$outdir/queue_drift_scan.json" "$qds_rc" "present"
    emit_status_bundle_json "$outdir" "$packet_sha" "$summary_sha" "$qds_rc" "present" 0 1
  else
    printf 'INFO: queue-drift-scan unavailable\n' > "$outdir/queue_drift_scan.txt"
    emit_queue_drift_scan_json "$outdir/queue_drift_scan.txt" "$outdir/queue_drift_scan.json" 0 "unavailable"
    emit_status_bundle_json "$outdir" "$packet_sha" "$summary_sha" 0 "unavailable" 0 1
  fi
  emit_kv_file_canonical "$outdir/versions.txt" \
    "git_sha=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)" \
    "python=$(python3 --version 2>/dev/null | tr -d '\r')" \
    "proof_packet_packet_sha=$packet_sha" \
    "proof_packet_summary_sha=$summary_sha"
  echo "INFO: proof-bundle output dir=$outdir"
}

emit_tool_events_jsonl(){
  local outdir="$1"
  cp "$TOOL_EVENTS_FILE" "$outdir/tool_events.jsonl"
}

emit_input_manifest_json(){
  local outdir="$1"
  python3 - <<'PY' "$outdir/input_manifest.json" "$outdir/tool_events.jsonl"
import hashlib
import json
import sys
from pathlib import Path

out_path = Path(sys.argv[1])
events_path = Path(sys.argv[2])
digests = set()

if events_path.is_file():
    for raw in events_path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        canonical = json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"
        digests.add("sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest())

doc = {
    "input_manifest_version": "v0",
    "inputs": [{"ref_type": "tool_event", "digest": d} for d in sorted(digests)],
}
out_path.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

emit_status_bundle_json(){
  local outdir="$1" packet_sha="$2" summary_sha="$3" qds_rc="$4" qds_status="$5" gate_rc="$6" gate_pass="$7"
  python3 - <<'PY' "$outdir/status_bundle.json" "$ROOT" "$GOV_PROFILE" "$STRICT_PROOF_PACKET" "$STRICT_PROOF_PACKET_SOURCE" "$packet_sha" "$summary_sha" "$qds_rc" "$qds_status" "$gate_rc" "$gate_pass"
import json, subprocess, sys
from pathlib import Path

out_path = Path(sys.argv[1])
root = Path(sys.argv[2])
gov_profile = sys.argv[3]
strict_value = sys.argv[4]
strict_source = sys.argv[5]
packet_sha = sys.argv[6]
summary_sha = sys.argv[7]
qds_rc = int(sys.argv[8])
qds_status = sys.argv[9]
gate_rc = int(sys.argv[10])
gate_pass = (sys.argv[11] == "1")

try:
    git_sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], text=True).strip()
except Exception:
    git_sha = "unknown"

doc = {
    "gov_profile": gov_profile,
    "proof_packet_sha256": packet_sha,
    "proof_packet_verify_summary_sha256": summary_sha,
    "queue_drift_scan": {"rc": qds_rc, "status": qds_status},
    "release_gate_result": {"pass": gate_pass, "rc": gate_rc},
    "repo_git_sha": git_sha,
    "status_bundle_version": "status_bundle_v1",
    "strictness": {"source": strict_source, "value": int(strict_value)},
}
out_path.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

emit_queue_drift_scan_json(){
  local txt_path="$1" out_path="$2" qds_rc="$3" qds_status="$4"
  python3 - <<'PY' "$txt_path" "$out_path" "$qds_rc" "$qds_status"
import hashlib, json, sys
from pathlib import Path
txt = Path(sys.argv[1]).read_text(encoding="utf-8")
doc = {
    "queue_drift_scan_version": "queue_drift_scan_v1",
    "rc": int(sys.argv[3]),
    "status": sys.argv[4],
    "text_sha256": hashlib.sha256(txt.encode("utf-8")).hexdigest(),
}
Path(sys.argv[2]).write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

resolve_proof_packet_strictness

if [[ "$SKIP_BASE" != "1" ]]; then
  run_cmd python3 -m py_compile scripts/policy-eval.py
  run_cmd python3 -m py_compile scripts/verify-record.py
  run_cmd python3 -m py_compile scripts/verify-chain.py
  run_cmd python3 -m py_compile scripts/replay-record.py
  run_cmd bash tests/test_signing_key_loading.sh
  run_cmd bash tests/test_signing_emit.sh
  run_cmd bash tests/test_verify_signatures.sh
fi

proof_packet_check
run_ci_external_validator
run_ci_contract_checks
