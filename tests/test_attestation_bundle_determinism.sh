#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACK="$ROOT/scripts/attest/bundle.py"
VERIFY="$ROOT/scripts/verify-attestation-bundle.py"
FIXTURE_DIR="$ROOT/tests/fixtures/attestation_bundle/sample"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task112-bundle-det.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

echo "--- T-BUNDLE-DET-001: same inputs, same bytes across repeated runs ---"
OUT1="$TMPDIR_LOCAL/repeat1.tar"
OUT2="$TMPDIR_LOCAL/repeat2.tar"
LOG1="$TMPDIR_LOCAL/repeat1.log"
LOG2="$TMPDIR_LOCAL/repeat2.log"

python3 "$PACK" pack --input-dir "$FIXTURE_DIR" --out "$OUT1" | tee "$LOG1"
python3 "$PACK" pack --input-dir "$FIXTURE_DIR" --out "$OUT2" | tee "$LOG2"

SHA1="$(sha256_file "$OUT1")"
SHA2="$(sha256_file "$OUT2")"
[[ "$SHA1" == "$SHA2" ]]
echo "BUNDLE_SHA256_RUN1=$SHA1"
echo "BUNDLE_SHA256_RUN2=$SHA2"
echo "PASS: repeated pack output bytes are identical"

echo
echo "--- T-BUNDLE-DET-002: deterministic across different cwd contexts ---"
OUT3="$TMPDIR_LOCAL/cwd_a.tar"
OUT4="$TMPDIR_LOCAL/cwd_b.tar"
DIRA="$TMPDIR_LOCAL/cwd_a"
DIRB="$TMPDIR_LOCAL/cwd_b"
mkdir -p "$DIRA" "$DIRB"
(
  cd "$DIRA"
  python3 "$PACK" pack --input-dir "$FIXTURE_DIR" --out "$OUT3" >/dev/null
)
(
  cd "$DIRB"
  python3 "$PACK" pack --input-dir "$FIXTURE_DIR" --out "$OUT4" >/dev/null
)
SHA3="$(sha256_file "$OUT3")"
SHA4="$(sha256_file "$OUT4")"
[[ "$SHA3" == "$SHA4" ]]
echo "BUNDLE_SHA256_CWD_A=$SHA3"
echo "BUNDLE_SHA256_CWD_B=$SHA4"
echo "PASS: cwd variance does not affect bundle bytes"

echo
echo "--- T-BUNDLE-DET-003: input change changes bundle hash (sanity) ---"
FIXTURE_COPY="$TMPDIR_LOCAL/fixture_changed"
cp -R "$FIXTURE_DIR" "$FIXTURE_COPY"
printf 'request payload changed\n' > "$FIXTURE_COPY/artifacts/request.txt"
OUT5="$TMPDIR_LOCAL/changed_input.tar"
python3 "$PACK" pack --input-dir "$FIXTURE_COPY" --out "$OUT5" >/dev/null
SHA5="$(sha256_file "$OUT5")"
[[ "$SHA5" != "$SHA1" ]]
echo "BUNDLE_SHA256_BASELINE=$SHA1"
echo "BUNDLE_SHA256_CHANGED_INPUT=$SHA5"
echo "PASS: changed input produces different bundle hash"

echo
echo "--- T-BUNDLE-DET-004: changed-input bundle still verifies (sanity) ---"
python3 "$VERIFY" "$OUT5"
echo "PASS: changed-input bundle verifies"

echo
echo "Summary: deterministic pack regression complete"
