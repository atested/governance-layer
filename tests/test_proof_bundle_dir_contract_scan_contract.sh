#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task181-dirscan-contract.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

sha256_normalized_output() {
  python3 - <<'PY' "$1" "$TMPDIR_LOCAL"
import hashlib, pathlib, re, sys
txt = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
txt = re.sub(re.escape(sys.argv[2]) + r'/[^ \n]*', '/tmp/TASK181', txt)
print(hashlib.sha256(txt.encode('utf-8')).hexdigest())
PY
}

make_bundle() {
  local dir="$1"
  mkdir -p "$dir"
  python3 - <<'PY' "$dir"
import io, json, tarfile, hashlib, sys
from pathlib import Path
out = Path(sys.argv[1])
manifest = {"proof_packet_version":"proof_packet_v1","files":{"record.json":{"sha256":"dummy","size_bytes":2}}}
with tarfile.open(out/"proof_packet.tar", "w") as tf:
    for name,data in [
        ("manifest.json", (json.dumps(manifest, sort_keys=True, separators=(",",":"))+"\n").encode()),
        ("payload/record.json", b"{}"),
    ]:
        ti = tarfile.TarInfo(name); ti.size=len(data); ti.mtime=0; ti.uid=0; ti.gid=0; ti.uname=''; ti.gname=''; ti.mode=0o644
        tf.addfile(ti, io.BytesIO(data))
packet_sha = hashlib.sha256((out/"proof_packet.tar").read_bytes()).hexdigest()
(out/"proof_packet.sha256").write_text(f"{packet_sha}  proof_packet.tar\n", encoding="utf-8")
(out/"proof_packet_verify_summary.json").write_text(json.dumps({"report_version":"proof_packet_verify_summary_v1","result":"PASS"}, sort_keys=True, separators=(",",":"))+"\n", encoding="utf-8")
(out/"release_gate_log.txt").write_text("result=PASS\nprofile=ci\n", encoding="utf-8")
(out/"versions.txt").write_text("repo_git_sha=deadbeef\npython=3.11\n", encoding="utf-8")
qtxt = "QUEUE_DRIFT_SCAN v1\nA) none\n"
(out/"queue_drift_scan.txt").write_text(qtxt, encoding="utf-8")
qsha = hashlib.sha256(qtxt.encode()).hexdigest()
(out/"queue_drift_scan.json").write_text(json.dumps({"queue_drift_scan_version":"queue_drift_scan_v1","rc":0,"status":"present","text_sha256":qsha}, sort_keys=True, separators=(",",":"))+"\n", encoding="utf-8")
status = {
    "status_bundle_version":"status_bundle_v1",
    "strictness":{"value":0},
    "repo_git_sha":"deadbeef",
    "gov_profile":"dev",
    "proof_packet_sha256":f"sha256:{packet_sha}",
    "proof_packet_verify_summary_sha256":"sha256:dummy",
    "release_gate_result":{"rc":0,"pass":True},
    "queue_drift_scan":{"rc":0,"status":"present"},
}
(out/"status_bundle.json").write_text(json.dumps(status, sort_keys=True, separators=(",",":"))+"\n", encoding="utf-8")
PY
}

run_scan() {
  local dir="$1" out="$2"
  set +e
  PROOF_BUNDLE_DIR="$dir" bash "$ROOT/tests/test_proof_bundle_dir_contract_scan.sh" >"$out" 2>&1
  local rc=$?
  set -e
  echo "$rc"
}

echo "--- T-PROOF-DIR-SCAN-CONTRACT-001: DIR_FILE_LIST ordering and pass output deterministic ---"
make_bundle "$TMPDIR_LOCAL/pass1"
make_bundle "$TMPDIR_LOCAL/pass2"
rc1="$(run_scan "$TMPDIR_LOCAL/pass1" "$TMPDIR_LOCAL/pass1.out")"
rc2="$(run_scan "$TMPDIR_LOCAL/pass2" "$TMPDIR_LOCAL/pass2.out")"
echo "PASS: PASS-case rc run1=$rc1 run2=$rc2"
[[ "$rc1" == "0" && "$rc2" == "0" ]] || { echo "FAIL: PASS-case rc mismatch"; exit 1; }
grep -q 'DIR_FILE_LIST=proof_packet.sha256,proof_packet.tar,proof_packet_verify_summary.json,queue_drift_scan.json,queue_drift_scan.txt,release_gate_log.txt,status_bundle.json,versions.txt' "$TMPDIR_LOCAL/pass1.out"
grep -q 'DIR_FILE_LIST=proof_packet.sha256,proof_packet.tar,proof_packet_verify_summary.json,queue_drift_scan.json,queue_drift_scan.txt,release_gate_log.txt,status_bundle.json,versions.txt' "$TMPDIR_LOCAL/pass2.out"
h1="$(sha256_normalized_output "$TMPDIR_LOCAL/pass1.out")"
h2="$(sha256_normalized_output "$TMPDIR_LOCAL/pass2.out")"
echo "DIRSCAN_PASS_SHA256_RUN1=$h1"
echo "DIRSCAN_PASS_SHA256_RUN2=$h2"
[[ "$h1" == "$h2" ]] || { echo "FAIL: PASS-case nondeterministic"; exit 1; }
echo "PASS: DIR_FILE_LIST ordering and PASS output deterministic"

echo "--- T-PROOF-DIR-SCAN-CONTRACT-002: malformed qds json linkage fails with stable marker ---"
make_bundle "$TMPDIR_LOCAL/fail1"
make_bundle "$TMPDIR_LOCAL/fail2"
python3 - <<'PY' "$TMPDIR_LOCAL/fail1/queue_drift_scan.json" "$TMPDIR_LOCAL/fail2/queue_drift_scan.json"
import json,sys,pathlib
for pth in sys.argv[1:]:
    p=pathlib.Path(pth); j=json.loads(p.read_text()); j["text_sha256"]="0"*64
    p.write_text(json.dumps(j, sort_keys=True, separators=(",",":"))+"\n", encoding="utf-8")
PY
fr1="$(run_scan "$TMPDIR_LOCAL/fail1" "$TMPDIR_LOCAL/fail1.out")"
fr2="$(run_scan "$TMPDIR_LOCAL/fail2" "$TMPDIR_LOCAL/fail2.out")"
echo "PASS: FAIL-case rc run1=$fr1 run2=$fr2"
[[ "$fr1" == "1" && "$fr2" == "1" ]] || { echo "FAIL: FAIL-case rc mismatch"; exit 1; }
grep -q 'FAIL: queue_drift_scan.json text_sha256 linkage mismatch' "$TMPDIR_LOCAL/fail1.out"
grep -q 'FAIL: queue_drift_scan.json text_sha256 linkage mismatch' "$TMPDIR_LOCAL/fail2.out"
fh1="$(sha256_normalized_output "$TMPDIR_LOCAL/fail1.out")"
fh2="$(sha256_normalized_output "$TMPDIR_LOCAL/fail2.out")"
echo "DIRSCAN_FAIL_SHA256_RUN1=$fh1"
echo "DIRSCAN_FAIL_SHA256_RUN2=$fh2"
[[ "$fh1" == "$fh2" ]] || { echo "FAIL: FAIL-case nondeterministic"; exit 1; }
echo "PASS: rejection marker deterministic across two runs"

echo "Summary: proof-bundle dir scanner contract ordering/rejection tests complete"
