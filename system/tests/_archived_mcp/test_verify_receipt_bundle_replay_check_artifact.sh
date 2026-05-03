#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_verify_receipt_bundle_replay_check_artifact"
OUT_A="out/test_verify_receipt_bundle_replay_check_artifact_A"
OUT_B="out/test_verify_receipt_bundle_replay_check_artifact_B"
rm -rf "$TMP_ROOT" "$OUT_A" "$OUT_B" out/mcp_exec
mkdir -p "$TMP_ROOT"

make_bundle() {
  local out_dir="$1"
  printf 'verify replay artifact\n' > "$TMP_ROOT/src.txt"
  python3 - "$ROOT" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])

exec_req = {
    "id": "EXEC",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_verify_receipt_bundle_replay_check_artifact/src.txt",
                "dst_path": "out/test_verify_receipt_bundle_replay_check_artifact/dst.txt",
                "overwrite": True,
            },
        },
        "mode": {"require_admissible": True, "dry_run": True, "run_id": "RID_VERIFY_REPLAY_ART"},
    },
}
proc = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(exec_req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if proc.returncode != 0:
    raise SystemExit("FAIL:EXEC_RC")

replay_req = {
    "id": "REPLAY",
    "method": "capabilities.replay_check",
    "params": {"run_id": "RID_VERIFY_REPLAY_ART", "policy_context": "STRICT_OUT_ONLY", "emit_artifact": True},
}
rp = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(replay_req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if rp.returncode != 0:
    raise SystemExit("FAIL:REPLAY_RC")
PY

  python3 scripts/attest/export_receipt_bundle.py --receipt-run-id RID_VERIFY_REPLAY_ART --out-dir "$out_dir" --include-signature 0 --include-replay-check 1 >/dev/null
}

normalize() {
  sed -E 's#out/test_verify_receipt_bundle_replay_check_artifact_[AB]#out/test_verify_receipt_bundle_replay_check_artifact_X#g'
}

make_bundle "$OUT_A"
PASS1="$(python3 scripts/verify-attestation-bundle.py "$OUT_A" 2>&1 | normalize)"
echo "$PASS1" | rg '^PASS: attestation bundle manifest \+ payload hashes verified$' >/dev/null

python3 - <<'PY'
from pathlib import Path
p = Path('out/test_verify_receipt_bundle_replay_check_artifact_A/payload/artifacts/replay_check.v0.json')
raw = p.read_text(encoding='utf-8')
p.write_text(raw.replace('"OUTSIDE_ALLOWED_ROOT"', '"BAD_TOKEN"', 1), encoding='utf-8')
PY

set +e
BAD1_RAW="$(python3 scripts/verify-attestation-bundle.py "$OUT_A" 2>&1)"
BAD1_RC=$?
set -e
BAD1="$(echo "$BAD1_RAW" | normalize)"
[[ $BAD1_RC -ne 0 ]] || { echo "FAIL:EXPECTED_TAMPER_FAIL"; exit 1; }
echo "$BAD1" | rg '^FAIL: (hash|size) mismatch for artifacts/replay_check\.v0\.json' >/dev/null

rm -rf "$OUT_A" out/mcp_exec
make_bundle "$OUT_B"
PASS2="$(python3 scripts/verify-attestation-bundle.py "$OUT_B" 2>&1 | normalize)"
echo "$PASS2" | rg '^PASS: attestation bundle manifest \+ payload hashes verified$' >/dev/null

python3 - <<'PY'
from pathlib import Path
p = Path('out/test_verify_receipt_bundle_replay_check_artifact_B/payload/artifacts/replay_check.v0.json')
raw = p.read_text(encoding='utf-8')
p.write_text(raw.replace('"OUTSIDE_ALLOWED_ROOT"', '"BAD_TOKEN"', 1), encoding='utf-8')
PY
set +e
BAD2_RAW="$(python3 scripts/verify-attestation-bundle.py "$OUT_B" 2>&1)"
BAD2_RC=$?
set -e
BAD2="$(echo "$BAD2_RAW" | normalize)"
[[ $BAD2_RC -ne 0 ]] || { echo "FAIL:EXPECTED_TAMPER_FAIL_2"; exit 1; }

N1="$TMP_ROOT/norm1.txt"
N2="$TMP_ROOT/norm2.txt"
printf '%s\n%s\n' "$PASS1" "$BAD1" > "$N1"
printf '%s\n%s\n' "$PASS2" "$BAD2" > "$N2"
H1="$(shasum -a 256 "$N1" | awk '{print $1}')"
H2="$(shasum -a 256 "$N2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "VERIFY_RECEIPT_BUNDLE_REPLAY_CHECK_ARTIFACT=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
