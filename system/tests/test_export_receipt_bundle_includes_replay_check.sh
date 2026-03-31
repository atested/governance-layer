#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/attestation_proof_contract_common.sh"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_export_receipt_bundle_includes_replay_check"
OUT_WITH="out/test_export_receipt_bundle_with_replay"
OUT_AUTO="out/test_export_receipt_bundle_auto_replay"
OUT_MISSING="out/test_export_receipt_bundle_missing_replay"
rm -rf "$TMP_ROOT" "$OUT_WITH" "$OUT_AUTO" "$OUT_MISSING" out/mcp_exec
mkdir -p "$TMP_ROOT"

run_once() {
  local out_file="$1"
  rm -rf "$OUT_WITH" "$OUT_AUTO" "$OUT_MISSING" out/mcp_exec
  mkdir -p "$TMP_ROOT"
  printf 'replay-export\n' > "$TMP_ROOT/src.txt"

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
                "src_path": "out/test_export_receipt_bundle_includes_replay_check/src.txt",
                "dst_path": "out/test_export_receipt_bundle_includes_replay_check/dst.txt",
                "overwrite": True,
            },
        },
        "mode": {"require_admissible": True, "dry_run": True, "run_id": "RID_REPLAY_EXPORT"},
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
    "params": {"run_id": "RID_REPLAY_EXPORT", "policy_context": "STRICT_OUT_ONLY", "emit_artifact": True},
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

  WITH_LINE="$(python3 scripts/attest/export_receipt_bundle.py --receipt-run-id RID_REPLAY_EXPORT --out-dir "$OUT_WITH" --include-signature 0 --include-replay-check 1)"
  attestation_proof_require_contains "$WITH_LINE" "RECEIPT_ATTESTATION_BUNDLE_EXPORT ok=yes reason=OK " "FAIL:WITH_CONTRACT"
  attestation_proof_require_kv_equal "$WITH_LINE" replay_check_present "yes" "FAIL:WITH_REPLAY_FLAG"
  [[ -f "$OUT_WITH/payload/artifacts/replay_check.v0.json" ]] || { echo "FAIL:REPLAY_FILE_MISSING"; exit 1; }
  python3 - "$OUT_WITH/manifest.json" <<'PY'
import json
import sys
m = json.load(open(sys.argv[1], encoding='utf-8'))
if m.get('replay_check_present') is not True:
    raise SystemExit('FAIL:REPLAY_PRESENT_FALSE')
paths = [f.get('path') for f in m.get('files', []) if isinstance(f, dict)]
if 'artifacts/replay_check.v0.json' not in paths:
    raise SystemExit('FAIL:REPLAY_NOT_IN_MANIFEST')
PY

  AUTO_LINE="$(python3 scripts/attest/export_receipt_bundle.py --receipt-run-id RID_REPLAY_EXPORT --out-dir "$OUT_AUTO" --include-signature 0 --include-replay-check 0)"
  attestation_proof_require_contains "$AUTO_LINE" "RECEIPT_ATTESTATION_BUNDLE_EXPORT ok=yes reason=OK " "FAIL:AUTO_CONTRACT"
  [[ -f "$OUT_AUTO/payload/artifacts/replay_check.v0.json" ]] || { echo "FAIL:REPLAY_AUTO_INCLUDE_MISSING"; exit 1; }

  printf 'missing\n' > "$TMP_ROOT/missing.txt"
  python3 - "$ROOT" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
req = {
    "id": "EXEC2",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_export_receipt_bundle_includes_replay_check/missing.txt",
                "dst_path": "out/test_export_receipt_bundle_includes_replay_check/missing_dst.txt",
                "overwrite": True,
            },
        },
        "mode": {"require_admissible": True, "dry_run": True, "run_id": "RID_REPLAY_MISSING"},
    },
}
proc = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if proc.returncode != 0:
    raise SystemExit("FAIL:EXEC2_RC")
PY

  set +e
  MISSING_RAW="$(python3 scripts/attest/export_receipt_bundle.py --receipt-run-id RID_REPLAY_MISSING --out-dir "$OUT_MISSING" --include-signature 0 --include-replay-check 1 2>&1)"
  MISSING_RC=$?
  set -e
  [[ $MISSING_RC -ne 0 ]] || { echo "FAIL:EXPECTED_REPLAY_MISSING_FAIL"; exit 1; }
  attestation_proof_require_contains "$MISSING_RAW" "RECEIPT_ATTESTATION_BUNDLE_EXPORT ok=no reason=REPLAY_ARTIFACT_MISSING " "FAIL:REPLAY_MISSING_TOKEN"

  python3 - "$OUT_WITH" "$OUT_AUTO" "$out_file" <<'PY'
import hashlib
import json
import pathlib
import sys

out_with = pathlib.Path(sys.argv[1])
out_auto = pathlib.Path(sys.argv[2])
out_file = pathlib.Path(sys.argv[3])

def digest_bundle(path: pathlib.Path) -> str:
    manifest = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
    parts = [json.dumps(manifest, sort_keys=True, separators=(',', ':'))]
    for rel in sorted(['payload/record.json', 'payload/artifacts/action_record.sha256', 'payload/artifacts/replay_check.v0.json']):
        p = path / rel
        if p.is_file():
            parts.append(rel + '=' + hashlib.sha256(p.read_bytes()).hexdigest())
    return hashlib.sha256('\n'.join(parts).encode('utf-8')).hexdigest()

summary = {
    'with': digest_bundle(out_with),
    'auto': digest_bundle(out_auto),
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
PY
}

RUN1="$TMP_ROOT/run1.json"
RUN2="$TMP_ROOT/run2.json"
run_once "$RUN1"
run_once "$RUN2"

_HASHES="$(attestation_proof_require_deterministic_files "$RUN1" "$RUN2" "FAIL:NON_DETERMINISTIC")"
H1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
H2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"

echo "EXPORT_RECEIPT_BUNDLE_INCLUDES_REPLAY_CHECK=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
