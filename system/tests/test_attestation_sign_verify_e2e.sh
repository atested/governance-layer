#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACK="$ROOT/scripts/attest/bundle.py"
VERIFY="$ROOT/scripts/verify-attestation-bundle.py"
KEY_PRIV="$ROOT/system/tests/fixtures/keys/ed25519_test_private.pem"
KEY_PUB="$ROOT/system/tests/fixtures/keys/ed25519_test_public.pem"

run_once() {
  local work="$1"
  rm -rf "$work"
  mkdir -p "$work/input/artifacts"

  cat > "$work/input/record.json" <<'JSON'
{"decision":"ALLOW","record_hash":"sha256:0000000000000000000000000000000000000000000000000000000000000000"}
JSON
  printf 'request\n' > "$work/input/artifacts/request.txt"
  printf 'response\n' > "$work/input/artifacts/response.txt"
  cat > "$work/input/artifacts/replay_audit_report.json" <<'JSON'
{"summary":"ok"}
JSON

  local bundle="$work/attestation_bundle.tar"
  python3 "$PACK" pack --input-dir "$work/input" --out "$bundle" >/dev/null

  python3 - "$ROOT" "$bundle" "$KEY_PRIV" <<'PY'
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / 'scripts' / 'attest'))
import ed25519_bundle_signing as s
s.write_signature_artifacts(pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3]), None, None)
print('BUNDLE_DIGEST=' + s.bundle_digest(pathlib.Path(sys.argv[2])))
PY

  local out_ok
  out_ok="$(python3 "$VERIFY" "$bundle" --require-signature 1 --pubkey "$KEY_PUB")"
  echo "$out_ok" | rg '^ATTESTATION_BUNDLE_VERIFY ok=yes reason=OK ' >/dev/null
  echo "$out_ok" | rg '^PASS: attestation bundle signature verified$' >/dev/null
  echo "$out_ok" | rg '^PASS: attestation bundle manifest \+ payload hashes verified$' >/dev/null
  echo "VERIFY_OK=YES"

  python3 - "$bundle" <<'PY'
import pathlib
import sys
p = pathlib.Path(sys.argv[1] + '.sig')
s = p.read_text(encoding='utf-8').strip()
p.write_text((s[:-1] + ('A' if s[-1] != 'A' else 'B')) + '\n', encoding='utf-8')
PY

  local out_bad rc_bad
  set +e
  out_bad="$(python3 "$VERIFY" "$bundle" --require-signature 1 --pubkey "$KEY_PUB" 2>&1)"
  rc_bad=$?
  set -e
  [[ $rc_bad -ne 0 ]]
  echo "$out_bad" | rg '^ATTESTATION_BUNDLE_VERIFY ok=no reason=SIGNATURE_INVALID ' >/dev/null
  echo "$out_bad" | rg '^FAIL: SIGNATURE_VERIFICATION_FAILED$' >/dev/null
  echo "VERIFY_TAMPER_FAIL=YES"
}

TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/attestation-sign-verify-e2e.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

RUN1="$TMPDIR_LOCAL/run1.txt"
RUN2="$TMPDIR_LOCAL/run2.txt"

run_once "$TMPDIR_LOCAL/work1" > "$RUN1"
run_once "$TMPDIR_LOCAL/work2" > "$RUN2"

H1="$(shasum -a 256 "$RUN1" | awk '{print $1}')"
H2="$(shasum -a 256 "$RUN2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL: NON_DETERMINISTIC"; exit 1; }

echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
echo "CASE=ATTESTATION_SIGN_VERIFY_E2E PASS"
