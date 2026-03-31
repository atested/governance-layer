#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task175-negctrl.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

make_valid_bundle() {
  local dir="$1"
  mkdir -p "$dir"
  python3 - <<'PY' "$dir"
import io, json, tarfile, sys, pathlib, hashlib
out = pathlib.Path(sys.argv[1])
(out/'versions.txt').write_text('repo_git_sha=deadbeef\npython_version=3.x\n', encoding='utf-8')
(out/'release_gate_log.txt').write_text('result=PASS\nprofile=ci\n', encoding='utf-8')
(out/'proof_packet_verify_summary.json').write_text(json.dumps({
  'report_version':'proof_packet_verify_summary_v1','result':'PASS'
}, sort_keys=True, separators=(',',':'))+'\n', encoding='utf-8')
manifest = {'proof_packet_version':'proof_packet_v1','files':{'record.json':{'sha256':'dummy','size_bytes':2}}}
tar_path = out/'proof_packet.tar'
with tarfile.open(tar_path, 'w') as tf:
    payload = json.dumps(manifest, sort_keys=True, separators=(',',':')).encode()+b'\n'
    ti = tarfile.TarInfo('manifest.json'); ti.size=len(payload); ti.mtime=0; ti.uid=0; ti.gid=0; ti.uname=''; ti.gname=''; ti.mode=0o644
    tf.addfile(ti, io.BytesIO(payload))
    rec = b'{}'
    ti = tarfile.TarInfo('payload/record.json'); ti.size=len(rec); ti.mtime=0; ti.uid=0; ti.gid=0; ti.uname=''; ti.gname=''; ti.mode=0o644
    tf.addfile(ti, io.BytesIO(rec))
h = hashlib.sha256(tar_path.read_bytes()).hexdigest()
(out/'proof_packet.sha256').write_text(f'{h}  proof_packet.tar\n', encoding='utf-8')
PY
}

run_case_twice() {
  local label="$1" expected_rc="$2" marker="$3" mutator="$4"
  local out1="$TMPDIR_LOCAL/${label}.1.out" out2="$TMPDIR_LOCAL/${label}.2.out"
  local b1="$TMPDIR_LOCAL/${label}.bundle1" b2="$TMPDIR_LOCAL/${label}.bundle2"
  rm -rf "$b1" "$b2"; mkdir -p "$b1" "$b2"
  make_valid_bundle "$b1"; make_valid_bundle "$b2"
  eval "$mutator \"$b1\""
  eval "$mutator \"$b2\""
  set +e
  bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$b1" >"$out1" 2>&1; rc1=$?
  bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$b2" >"$out2" 2>&1; rc2=$?
  set -e
  echo "PASS: $label rc run1=$rc1 run2=$rc2"
  [[ $rc1 -eq $expected_rc && $rc2 -eq $expected_rc ]] || { echo "FAIL: $label unexpected rc"; return 1; }
  grep -q "$marker" "$out1" && grep -q "$marker" "$out2" || { echo "FAIL: $label missing marker"; return 1; }
  h1="$(sha256_file "$out1")"; h2="$(sha256_file "$out2")"
  echo "${label}_SHA256_RUN1=$h1"
  echo "${label}_SHA256_RUN2=$h2"
  [[ "$h1" = "$h2" ]] || { echo "FAIL: $label nondeterministic output"; return 1; }
  echo "PASS: $label deterministic failure output"
}

rm_file() { rm -f "$1/$2"; }
checksum_mismatch() { printf '0%.0s' {1..64}; echo '  proof_packet.tar'; } # helper not used directly

mut_rm_proof_packet_tar() { rm -f "$1/proof_packet.tar"; }
mut_rm_sha() { rm -f "$1/proof_packet.sha256"; }
mut_rm_summary() { rm -f "$1/proof_packet_verify_summary.json"; }
mut_rm_log() { rm -f "$1/release_gate_log.txt"; }
mut_rm_versions() { rm -f "$1/versions.txt"; }
mut_sha_mismatch() { python3 - <<'PY' "$1/proof_packet.sha256"
from pathlib import Path; p=Path(__import__('sys').argv[1]); p.write_text('0'*64+'  proof_packet.tar\n', encoding='utf-8')
PY
}
mut_sha_upper() { python3 - <<'PY' "$1/proof_packet.sha256"
from pathlib import Path; p=Path(__import__('sys').argv[1]); line=p.read_text(); p.write_text(line.upper(), encoding='utf-8')
PY
}
mut_sha_wronglen() { python3 - <<'PY' "$1/proof_packet.sha256"
from pathlib import Path; p=Path(__import__('sys').argv[1]); p.write_text('abc123  proof_packet.tar\n', encoding='utf-8')
PY
}
mut_sha_missing_filename() { python3 - <<'PY' "$1/proof_packet.sha256"
from pathlib import Path; p=Path(__import__('sys').argv[1]); p.write_text('0'*64+'\n', encoding='utf-8')
PY
}
mut_sha_extra_fields() { python3 - <<'PY' "$1/proof_packet.sha256"
from pathlib import Path; p=Path(__import__('sys').argv[1]); p.write_text('0'*64+'  proof_packet.tar  extra\n', encoding='utf-8')
PY
}

echo '--- T-VALIDATE-NEG-001: missing required files fail deterministically ---'
run_case_twice MISSING_PROOF_PACKET_TAR 1 'FAIL: missing required file: proof_packet.tar' mut_rm_proof_packet_tar
run_case_twice MISSING_SHA_FILE 1 'FAIL: missing required file: proof_packet.sha256' mut_rm_sha
run_case_twice MISSING_SUMMARY_FILE 1 'FAIL: missing required file: proof_packet_verify_summary.json' mut_rm_summary
run_case_twice MISSING_RELEASE_GATE_LOG 1 'FAIL: missing required file: release_gate_log.txt' mut_rm_log
run_case_twice MISSING_VERSIONS 1 'FAIL: missing required file: versions.txt' mut_rm_versions

echo '--- T-VALIDATE-NEG-002: checksum mismatch fails deterministically ---'
run_case_twice SHA_MISMATCH 1 'FAIL: proof_packet.sha256 mismatch' mut_sha_mismatch

echo '--- T-VALIDATE-NEG-003: malformed sha file formats fail deterministically ---'
run_case_twice SHA_UPPERCASE 1 'FAIL: proof_packet.sha256 format invalid' mut_sha_upper
run_case_twice SHA_WRONGLEN 1 'FAIL: proof_packet.sha256 format invalid' mut_sha_wronglen
run_case_twice SHA_MISSING_FILENAME 1 'FAIL: proof_packet.sha256 format invalid' mut_sha_missing_filename
run_case_twice SHA_EXTRA_FIELDS 1 'FAIL: proof_packet.sha256 format invalid' mut_sha_extra_fields

echo 'Summary: validator negative-controls matrix complete'
