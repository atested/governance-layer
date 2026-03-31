#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL=""

cleanup() {
  if [[ -n "${TMPDIR_LOCAL:-}" && -d "$TMPDIR_LOCAL" ]]; then
    rm -rf "$TMPDIR_LOCAL"
  fi
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*"
  exit 1
}

runtime_error() {
  echo "RUNTIME_ERROR: $*"
  exit 2
}

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())
PY
}

check_qds_txt() {
  local f="$1"
  python3 - <<'PY' "$f"
from pathlib import Path
import sys
s = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
if not s:
    print("FAIL: queue_drift_scan.txt empty")
    raise SystemExit(1)
if s.startswith("INFO: queue-drift-scan unavailable"):
    print("PASS: queue_drift_scan.txt sentinel allowed")
else:
    print("PASS: queue_drift_scan.txt non-empty human text allowed")
raise SystemExit(0)
PY
}

check_qds_json() {
  local json_file="$1"
  local txt_file="$2"
  python3 - <<'PY' "$json_file" "$txt_file"
from pathlib import Path
import hashlib, json, sys
jp = Path(sys.argv[1])
tp = Path(sys.argv[2])
j = json.loads(jp.read_text(encoding="utf-8"))
if j.get("queue_drift_scan_version") != "queue_drift_scan_v1":
    print("FAIL: queue_drift_scan.json version mismatch")
    raise SystemExit(1)
if not isinstance(j.get("rc"), int):
    print("FAIL: queue_drift_scan.json rc not int")
    raise SystemExit(1)
status = j.get("status")
if status not in ("present", "unavailable"):
    print("FAIL: queue_drift_scan.json status invalid")
    raise SystemExit(1)
txt_digest = hashlib.sha256(tp.read_bytes()).hexdigest()
if j.get("text_sha256") != txt_digest:
    print("FAIL: queue_drift_scan.json text_sha256 linkage mismatch")
    raise SystemExit(1)
print("PASS: queue_drift_scan.json schema/version and text digest linkage valid")
PY
}

check_status_bundle() {
  local f="$1"
  python3 - <<'PY' "$f"
from pathlib import Path
import json, sys
j = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if j.get("status_bundle_version") != "status_bundle_v1":
    print("FAIL: status_bundle.json version mismatch")
    raise SystemExit(1)
strictness = j.get("strictness")
if not isinstance(strictness, dict):
    print("FAIL: status_bundle.json strictness missing")
    raise SystemExit(1)
val = strictness.get("value")
if not isinstance(val, int) or val not in (0, 1):
    print("FAIL: status_bundle.json strictness.value not int 0|1")
    raise SystemExit(1)
required = ["repo_git_sha", "gov_profile", "proof_packet_sha256", "proof_packet_verify_summary_sha256", "release_gate_result", "queue_drift_scan"]
missing = [k for k in required if k not in j]
if missing:
    print("FAIL: status_bundle.json missing keys: " + ",".join(sorted(missing)))
    raise SystemExit(1)
print("PASS: status_bundle.json schema/version and strictness typing valid")
PY
}

build_selftest_bundle() {
  TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task170-selftest.XXXXXX")"
  local d="$TMPDIR_LOCAL/proof-bundles/selftest"
  mkdir -p "$d"
  printf 'tar-bytes-placeholder\n' > "$d/proof_packet.tar"
  local packet_sha
  packet_sha="$(sha256_file "$d/proof_packet.tar")"
  printf '%s  proof_packet.tar\n' "$packet_sha" > "$d/proof_packet.sha256"
  printf '{\"report_version\":\"proof_packet_verify_summary_v1\"}\n' > "$d/proof_packet_verify_summary.json"
  printf 'gate_result=pass\nprofile=dev\n' > "$d/release_gate_log.txt"
  printf 'git_sha=deadbeef\npython_version=3.11.0\n' > "$d/versions.txt"
  printf 'QUEUE_DRIFT_SCAN v1\nA) sample line\n' > "$d/queue_drift_scan.txt"
  local qds_sha
  qds_sha="$(sha256_file "$d/queue_drift_scan.txt")"
  python3 - <<'PY' "$d/queue_drift_scan.json" "$qds_sha"
import json, sys
out = {
  "queue_drift_scan_version": "queue_drift_scan_v1",
  "rc": 0,
  "status": "present",
  "text_sha256": sys.argv[2],
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n")
PY
  python3 - <<'PY' "$d/status_bundle.json" "$packet_sha"
import json, sys
out = {
  "status_bundle_version": "status_bundle_v1",
  "repo_git_sha": "deadbeef",
  "gov_profile": "dev",
  "strictness": {"source": "profile", "value": 0},
  "proof_packet_sha256": f"sha256:{sys.argv[2]}",
  "proof_packet_verify_summary_sha256": "sha256:dummy",
  "release_gate_result": {"pass": True, "rc": 0},
  "queue_drift_scan": {"rc": 0, "status": "present"},
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n")
PY
  echo "$d"
}

main() {
  local dir="${PROOF_BUNDLE_DIR:-}"
  if [[ "${TASK170_SELFTEST:-0}" == "1" ]]; then
    dir="$(build_selftest_bundle)"
    echo "INFO: TASK170 selftest bundle generated"
  fi
  [[ -n "$dir" ]] || runtime_error "PROOF_BUNDLE_DIR env var required"
  [[ -d "$dir" ]] || runtime_error "PROOF_BUNDLE_DIR not found: $dir"

  local required=(
    proof_packet.tar
    proof_packet.sha256
    proof_packet_verify_summary.json
    release_gate_log.txt
    versions.txt
  )

  echo "--- T-PROOF-BUNDLE-DIR-SCAN-001: required files + optional semantics ---"
  for name in "${required[@]}"; do
    if [[ -f "$dir/$name" ]]; then
      echo "PASS: required file present: $name"
    else
      fail "missing required file: $name"
    fi
  done

  if [[ -f "$dir/queue_drift_scan.txt" ]]; then
    check_qds_txt "$dir/queue_drift_scan.txt"
    if [[ -f "$dir/queue_drift_scan.json" ]]; then
      check_qds_json "$dir/queue_drift_scan.json" "$dir/queue_drift_scan.txt"
    else
      echo "INFO: queue_drift_scan.json absent (optional)"
    fi
  else
    if [[ -f "$dir/queue_drift_scan.json" ]]; then
      fail "queue_drift_scan.json present without queue_drift_scan.txt"
    fi
    echo "INFO: queue_drift_scan.txt absent (optional)"
    echo "INFO: queue_drift_scan.json absent (optional)"
  fi

  if [[ -f "$dir/status_bundle.json" ]]; then
    check_status_bundle "$dir/status_bundle.json"
  else
    echo "INFO: status_bundle.json absent (optional)"
  fi

  local listing
  listing="$(find "$dir" -maxdepth 1 -type f -print | sed 's#^.*/##' | LC_ALL=C sort | paste -sd, -)"
  echo "DIR_FILE_LIST=$listing"
}

main "$@"
