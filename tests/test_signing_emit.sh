#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
TEST_KEY_FILE="$ROOT/system/tests/fixtures/keys/ed25519_test_private.pem"
TMPDIR=$(mktemp -d)
cleanup(){ rm -rf "$TMPDIR"; }
trap cleanup EXIT

KEY_PATH="$TMPDIR/key.pem"
PUB_PATH="$TMPDIR/key.pub.pem"
cp "$TEST_KEY_FILE" "$KEY_PATH"

python3 <<PY
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
key = Path("$KEY_PATH")
priv = serialization.load_pem_private_key(key.read_bytes(), password=None)
pub = priv.public_key()
pub_pem = pub.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)
Path("$PUB_PATH").write_bytes(pub_pem)
PY

FIXTURE="$ROOT/tests/fixtures/canon_001a.json"
RECORD1="$TMPDIR/record1.json"
RECORD2="$TMPDIR/record2.json"

env GOV_SIGNING_KEY_PATH="$KEY_PATH" python3 "$ROOT/scripts/policy-eval.py" "$FIXTURE" >"$RECORD1"
env GOV_SIGNING_KEY_PATH="$KEY_PATH" python3 "$ROOT/scripts/policy-eval.py" "$FIXTURE" >"$RECORD2"

python3 <<PY
import json
from pathlib import Path
r1=json.loads(Path("$RECORD1").read_text(encoding="utf-8"))
r2=json.loads(Path("$RECORD2").read_text(encoding="utf-8"))
assert r1.get("signature")
assert r1.get("signing_key_id")
assert r1["signature"] == r2["signature"]
assert r1["signing_key_id"] == r2["signing_key_id"]
assert r1["record_hash"] == r2["record_hash"]
print(f"SIGNING_KEY_ID={r1['signing_key_id']}")
print(f"SIGNATURE={r1['signature']}")
print(f"RECORD_HASH={r1['record_hash']}")
PY

env GOV_VERIFY_KEY_PATH="$PUB_PATH" python3 "$ROOT/scripts/verify-record.py" "$RECORD1"
