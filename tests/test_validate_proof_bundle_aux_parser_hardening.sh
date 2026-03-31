#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task176-aux-parser.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT
sha256_file(){ python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}
make_valid_bundle(){
  local dir="$1"
  mkdir -p "$dir"
  python3 - <<'PY' "$dir"
import io,json,tarfile,hashlib,sys,pathlib
out=pathlib.Path(sys.argv[1])
(out/'versions.txt').write_text('repo_git_sha=deadbeef\npython=3.11\n', encoding='utf-8')
(out/'release_gate_log.txt').write_text('result=PASS\nprofile=ci\n', encoding='utf-8')
(out/'proof_packet_verify_summary.json').write_text(json.dumps({'report_version':'proof_packet_verify_summary_v1','result':'PASS'}, sort_keys=True, separators=(',',':'))+'\n', encoding='utf-8')
manifest={'proof_packet_version':'proof_packet_v1','files':{'record.json':{'sha256':'dummy','size_bytes':2}}}
with tarfile.open(out/'proof_packet.tar','w') as tf:
    for name,data in [('manifest.json', json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()+b'\n'), ('payload/record.json', b'{}')]:
        ti=tarfile.TarInfo(name); ti.size=len(data); ti.mtime=0; ti.uid=0; ti.gid=0; ti.uname=''; ti.gname=''; ti.mode=0o644
        tf.addfile(ti, io.BytesIO(data))
h=hashlib.sha256((out/'proof_packet.tar').read_bytes()).hexdigest()
(out/'proof_packet.sha256').write_text(f'{h}  proof_packet.tar\n', encoding='utf-8')
PY
}
run_case(){
  local label="$1" rc_expected="$2" marker="$3" mutator="$4"
  local b1="$TMPDIR_LOCAL/${label}.1" b2="$TMPDIR_LOCAL/${label}.2" o1="$TMPDIR_LOCAL/${label}.1.out" o2="$TMPDIR_LOCAL/${label}.2.out"
  make_valid_bundle "$b1"; make_valid_bundle "$b2"
  eval "$mutator \"$b1\""
  eval "$mutator \"$b2\""
  set +e
  bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$b1" >"$o1" 2>&1; r1=$?
  bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$b2" >"$o2" 2>&1; r2=$?
  set -e
  echo "PASS: $label rc run1=$r1 run2=$r2"
  [[ $r1 -eq $rc_expected && $r2 -eq $rc_expected ]] || { echo "FAIL: $label rc mismatch"; return 1; }
  grep -q "$marker" "$o1" && grep -q "$marker" "$o2" || { echo "FAIL: $label marker missing"; return 1; }
  h1=$(sha256_file "$o1"); h2=$(sha256_file "$o2")
  echo "${label}_SHA256_RUN1=$h1"; echo "${label}_SHA256_RUN2=$h2"
  [[ "$h1" = "$h2" ]] || { echo "FAIL: $label nondeterministic"; return 1; }
  echo "PASS: $label deterministic taxonomy output"
}
mut_dup_versions(){ printf 'repo_git_sha=deadbeef\nrepo_git_sha=beadfeed\n' > "$1/versions.txt"; }
mut_malformed_versions(){ printf 'repo_git_sha=deadbeef\nMALFORMED\n' > "$1/versions.txt"; }
mut_emptykey_versions(){ printf '=value\n' > "$1/versions.txt"; }
mut_dup_log(){ printf 'result=PASS\nresult=FAIL\n' > "$1/release_gate_log.txt"; }
mut_malformed_log(){ printf 'result=PASS\n profile=ci\n' > "$1/release_gate_log.txt"; }

echo '--- T-VALIDATE-AUX-001: duplicate/malformed versions.txt and release_gate_log.txt fail deterministically ---'
run_case DUP_VERSIONS 1 'FAIL:versions.txt:line2:duplicate_key:repo_git_sha' mut_dup_versions
run_case MALFORMED_VERSIONS 1 'FAIL:versions.txt:line2:missing_equals' mut_malformed_versions
run_case EMPTYKEY_VERSIONS 1 'FAIL:versions.txt:line1:empty_key' mut_emptykey_versions
run_case DUP_RELEASE_GATE_LOG 1 'FAIL:release_gate_log.txt:line2:duplicate_key:result' mut_dup_log
run_case MALFORMED_RELEASE_GATE_LOG 1 'FAIL:release_gate_log.txt:line2:spaces_around_equals' mut_malformed_log

echo '--- T-VALIDATE-AUX-002: runtime error taxonomy deterministic (missing bundle dir) ---'
set +e
bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$TMPDIR_LOCAL/DOES_NOT_EXIST" >"$TMPDIR_LOCAL/rt1.out" 2>&1; rr1=$?
bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$TMPDIR_LOCAL/DOES_NOT_EXIST" >"$TMPDIR_LOCAL/rt2.out" 2>&1; rr2=$?
set -e
echo "PASS: RUNTIME_MISSING_DIR rc run1=$rr1 run2=$rr2"
[[ $rr1 -eq 1 && $rr2 -eq 1 ]] || { echo 'FAIL: runtime taxonomy unexpected rc'; exit 1; }
grep -q 'FAIL: bundle directory not found:' "$TMPDIR_LOCAL/rt1.out"
grep -q 'FAIL: bundle directory not found:' "$TMPDIR_LOCAL/rt2.out"
rh1=$(sha256_file "$TMPDIR_LOCAL/rt1.out"); rh2=$(sha256_file "$TMPDIR_LOCAL/rt2.out")
echo "RUNTIME_MISSING_DIR_SHA256_RUN1=$rh1"; echo "RUNTIME_MISSING_DIR_SHA256_RUN2=$rh2"
[[ "$rh1" = "$rh2" ]] || { echo 'FAIL: runtime taxonomy nondeterministic'; exit 1; }
echo 'PASS: runtime taxonomy deterministic output'

echo 'Summary: validator aux parser hardening checks complete'
