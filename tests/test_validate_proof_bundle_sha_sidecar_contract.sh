#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task180-sha-sidecar.XXXXXX")"
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
txt = re.sub(re.escape(sys.argv[2]) + r'/[^ \n]*', '/tmp/TASK180', txt)
txt = re.sub(r'^BUNDLE_DIR=.*$', 'BUNDLE_DIR=/tmp/TASK180', txt, flags=re.M)
print(hashlib.sha256(txt.encode('utf-8')).hexdigest())
PY
}

make_valid_bundle() {
  local dir="$1"
  mkdir -p "$dir"
  python3 - <<'PY' "$dir"
import io, json, tarfile, hashlib, sys
from pathlib import Path
out = Path(sys.argv[1])
manifest = {"proof_packet_version":"proof_packet_v1","files":{"record.json":{"sha256":"dummy","size_bytes":2}}}
with tarfile.open(out/"proof_packet.tar", "w") as tf:
    for name,data in [
        ("manifest.json", (json.dumps(manifest, sort_keys=True, separators=(",",":")) + "\n").encode()),
        ("payload/record.json", b"{}"),
    ]:
        ti = tarfile.TarInfo(name); ti.size=len(data); ti.mtime=0; ti.uid=0; ti.gid=0; ti.uname=''; ti.gname=''; ti.mode=0o644
        tf.addfile(ti, io.BytesIO(data))
packet_sha = hashlib.sha256((out/"proof_packet.tar").read_bytes()).hexdigest()
(out/"proof_packet.sha256").write_text(f"{packet_sha}  proof_packet.tar\n", encoding="utf-8")
(out/"proof_packet_verify_summary.json").write_text(json.dumps({"report_version":"proof_packet_verify_summary_v1","result":"PASS"}, sort_keys=True, separators=(",",":"))+"\n", encoding="utf-8")
(out/"release_gate_log.txt").write_text("result=PASS\nprofile=ci\n", encoding="utf-8")
(out/"versions.txt").write_text("repo_git_sha=deadbeef\npython=3.11\n", encoding="utf-8")
print(packet_sha)
PY
}

set_sha_line() {
  local dir="$1" style="$2"
  local sha
  sha="$(python3 - <<'PY' "$dir/proof_packet.tar"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
)"
  case "$style" in
    canonical) printf '%s  proof_packet.tar\n' "$sha" > "$dir/proof_packet.sha256" ;;
    single_space) printf '%s proof_packet.tar\n' "$sha" > "$dir/proof_packet.sha256" ;;
    tab_tab) printf '%s\t\tproof_packet.tar\n' "$sha" > "$dir/proof_packet.sha256" ;;
    space_tab) printf '%s \tproof_packet.tar\n' "$sha" > "$dir/proof_packet.sha256" ;;
    crlf) printf '%s  proof_packet.tar\r\n' "$sha" > "$dir/proof_packet.sha256" ;;
    trailing_space) printf '%s  proof_packet.tar \n' "$sha" > "$dir/proof_packet.sha256" ;;
    *) echo "unknown style $style" >&2; return 2 ;;
  esac
}

run_case() {
  local label="$1" style="$2" expected_rc="$3" marker="$4"
  local b1="$TMPDIR_LOCAL/${label}.1" b2="$TMPDIR_LOCAL/${label}.2"
  local o1="$TMPDIR_LOCAL/${label}.1.out" o2="$TMPDIR_LOCAL/${label}.2.out"
  make_valid_bundle "$b1" >/dev/null
  make_valid_bundle "$b2" >/dev/null
  set_sha_line "$b1" "$style"
  set_sha_line "$b2" "$style"
  set +e
  bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$b1" >"$o1" 2>&1; r1=$?
  bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$b2" >"$o2" 2>&1; r2=$?
  set -e
  echo "PASS: $label rc run1=$r1 run2=$r2"
  [[ $r1 -eq $expected_rc && $r2 -eq $expected_rc ]] || { echo "FAIL: $label rc mismatch"; return 1; }
  grep -q "$marker" "$o1" && grep -q "$marker" "$o2" || { echo "FAIL: $label marker missing"; return 1; }
  local h1 h2
  h1="$(sha256_normalized_output "$o1")"; h2="$(sha256_normalized_output "$o2")"
  echo "${label}_SHA256_RUN1=$h1"
  echo "${label}_SHA256_RUN2=$h2"
  [[ "$h1" == "$h2" ]] || { echo "FAIL: $label nondeterministic"; return 1; }
  echo "PASS: $label deterministic validator output"
}

echo "--- T-VALIDATE-SHA-SIDECAR-001: accepted canonical/two-whitespace forms deterministic ---"
run_case SHA_CANONICAL canonical 0 'PASS: proof-bundle external contract valid'
run_case SHA_TAB_TAB_ACCEPTED tab_tab 0 'PASS: proof-bundle external contract valid'
run_case SHA_SPACE_TAB_ACCEPTED space_tab 0 'PASS: proof-bundle external contract valid'

echo "--- T-VALIDATE-SHA-SIDECAR-002: rejected whitespace/line-ending forms deterministic ---"
run_case SHA_SINGLE_SPACE_REJECTED single_space 1 'FAIL: proof_packet.sha256 format invalid'
run_case SHA_CRLF_REJECTED crlf 1 'FAIL: proof_packet.sha256 format invalid'
run_case SHA_TRAILING_SPACE_REJECTED trailing_space 1 'FAIL: proof_packet.sha256 format invalid'

echo "Summary: validator sha sidecar whitespace/line-ending contract tests complete"
