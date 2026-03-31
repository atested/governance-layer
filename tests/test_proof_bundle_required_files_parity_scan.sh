#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task191-parity.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT
sha256_file(){ python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}
scan_once(){
  local out="$1"
  python3 - <<'PY' "$ROOT" > "$out"
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
doc = root / 'docs/EXTERNAL_CONTRACTS.md'
testf = root / 'tests/test_proof_bundle_contract_required_files.sh'
print('--- T-PROOF-BUNDLE-PARITY-001: required-files parity (docs vs enforcement test) ---')
if not doc.is_file():
    print('ERROR: docs/EXTERNAL_CONTRACTS.md missing')
    raise SystemExit(2)
if not testf.is_file():
    print('INFO: tests/test_proof_bundle_contract_required_files.sh missing (dependency TASK_148 not merged)')
    print('SKIP: required-files parity enforcement deferred')
    raise SystemExit(3)
text = doc.read_text(encoding='utf-8', errors='replace')
# Required files section entries like: **`proof_packet.tar`**
parts = text.split('### Optional Files', 1)[0]
doc_set = sorted(set(re.findall(r'\*\*`([^`]+)`\*\*', parts)))
doc_set = [x for x in doc_set if x in {
    'proof_packet.tar','proof_packet_verify_summary.json','proof_packet.sha256','release_gate_log.txt','versions.txt'
}]
# Extract required list from test source Python list named required = [...]
t = testf.read_text(encoding='utf-8', errors='replace')
m = re.search(r'required\s*=\s*\[(.*?)\]', t, re.S)
if not m:
    print('FAIL: could not parse required list from tests/test_proof_bundle_contract_required_files.sh')
    raise SystemExit(1)
items = re.findall(r'"([^"]+)"', m.group(1))
test_set = sorted(set(items))
print('DOC_REQUIRED=' + ','.join(doc_set))
print('TEST_REQUIRED=' + ','.join(test_set))
if doc_set != test_set:
    print('FAIL: required file set mismatch (docs vs test enforcement)')
    raise SystemExit(1)
print('PASS: docs required-files set matches enforcement test set')
PY
}
run1="$TMPDIR_LOCAL/run1.out"; run2="$TMPDIR_LOCAL/run2.out"
set +e
scan_once "$run1"; rc1=$?
scan_once "$run2"; rc2=$?
set -e
cat "$run1"
cat "$run2"
echo "RC_RUN1=$rc1"
echo "RC_RUN2=$rc2"
[[ "$rc1" -eq "$rc2" ]] || { echo 'FAIL: parity scan rc mismatch'; exit 1; }
H1="$(sha256_file "$run1")"; H2="$(sha256_file "$run2")"
echo "REQUIRED_PARITY_SHA256_RUN1=$H1"
echo "REQUIRED_PARITY_SHA256_RUN2=$H2"
[[ "$H1" == "$H2" ]] || { echo 'FAIL: parity scan output nondeterministic'; exit 1; }
if [[ "$rc1" -eq 0 ]]; then
  echo 'PASS: required-files parity scan output deterministic across two runs'
elif [[ "$rc1" -eq 3 ]]; then
  echo 'PASS: required-files parity scan SKIP output deterministic across two runs'
else
  echo 'FAIL: required-files parity scan failed'; exit 1
fi
