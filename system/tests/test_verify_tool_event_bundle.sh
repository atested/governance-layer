#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_event_contract_common.sh"
tool_event_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_verify_tool_event_bundle"
RUNTIME_DIR="$TMP_ROOT/runtime"
RESULT_DIR="out/test_verify_tool_event_bundle_results"
rm -rf "$TMP_ROOT" out/mcp_exec out/mcp_ingest_tool_event
rm -rf "$RESULT_DIR"
mkdir -p "$TMP_ROOT" "$RESULT_DIR"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" out/mcp_exec out/mcp_ingest_tool_event
  mkdir -p "$TMP_ROOT"

  GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 - "$ROOT" "$out_file" <<'PY'
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])


def rpc(req):
    proc = subprocess.run(
        ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
        input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("FAIL:RPC_RC")
    payload = json.loads(proc.stdout.strip())
    return payload["result"]


def run_cmd(args):
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    return proc.returncode, proc.stdout.strip()


params_digest = "sha256:" + hashlib.sha256(b"verify-bundle-params").hexdigest()
out_digest = "sha256:" + hashlib.sha256(b"verify-bundle-output").hexdigest()
ingest_req = {
    "id": "INGEST_FOR_VERIFY",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "INGEST_TOOL_EVENT",
            "params": {
                "tool_event_version": "v0",
                "tool_name": "TEST_TOOL_VERIFY_BUNDLE",
                "tool_params_digest": params_digest,
                "exit_code": 0,
                "outputs": [{"name": "stdout", "digest": out_digest, "ref_type": "blob"}],
                "provenance": {"source_identifier": "TEST_SRC", "extraction_date": "2026-03-06"},
                "policy_context_used": "DEFAULT",
            },
        },
        "mode": {"require_admissible": True, "dry_run": False, "run_id": "RID_TOOL_EVENT_VERIFY"},
    },
}
res = rpc(ingest_req)
if res.get("executed") is not True:
    raise SystemExit("FAIL:INGEST_FAILED")
digest = str(res["ingest_result"]["tool_event_sha256"])

bundle_rel = "out/test_verify_tool_event_bundle/BUNDLE_OK"
bundle_dir = root / bundle_rel
proc = subprocess.run(
    [
        "python3",
        str(root / "scripts/attest/export_tool_event_bundle.py"),
        "--digest",
        digest,
        "--out-dir",
        bundle_rel,
    ],
    text=True,
    capture_output=True,
    check=False,
)
if proc.returncode != 0:
    raise SystemExit("FAIL:EXPORT_FAILED")

ok_rc, ok_out = run_cmd(
    [
        "python3",
        str(root / "scripts/attest/verify_tool_event_bundle.py"),
        "--bundle-dir",
        str(bundle_dir),
    ]
)
if ok_rc != 0:
    raise SystemExit("FAIL:VERIFY_OK_PATH")
if "TOOL_EVENT_BUNDLE_VERIFY ok=yes reason=OK " not in ok_out:
    raise SystemExit("FAIL:VERIFY_OK_SHAPE")

manifest = json.loads((bundle_dir / "tool_event_bundle.manifest.json").read_text(encoding="utf-8"))
rel_payload = next(iter(manifest["files"].keys()))
payload_path = bundle_dir / rel_payload
data = bytearray(payload_path.read_bytes())
if not data:
    raise SystemExit("FAIL:EMPTY_PAYLOAD")
data[0] = (data[0] + 1) % 256
payload_path.write_bytes(bytes(data))

bad_rc, bad_out = run_cmd(
    [
        "python3",
        str(root / "scripts/attest/verify_tool_event_bundle.py"),
        "--bundle-dir",
        str(bundle_dir),
    ]
)
if bad_rc == 0:
    raise SystemExit("FAIL:VERIFY_BAD_RC")
if "TOOL_EVENT_BUNDLE_VERIFY ok=no reason=HASH_MISMATCH " not in bad_out:
    raise SystemExit("FAIL:VERIFY_BAD_REASON")

summary = {
    "digest": digest,
    "ok_output": ok_out,
    "bad_output": bad_out,
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$RESULT_DIR/run1.json"
R2="$RESULT_DIR/run2.json"
run_once "$R1"
run_once "$R2"

_HASHES="$(tool_event_require_deterministic_files "$R1" "$R2" "FAIL:NON_DETERMINISTIC")"
H1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
H2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"

OK_LINE="$(python3 scripts/attest/verify_tool_event_bundle.py --bundle-dir out/test_verify_tool_event_bundle/BUNDLE_OK || true)"
tool_event_require_status_line "$OK_LINE" "TOOL_EVENT_BUNDLE_VERIFY " "FAIL:CLI_CONTRACT_POST_TAMPER" \
  ok=no reason=HASH_MISMATCH bundle_version=tool_event_bundle_v0 tool_event_digests_count=1
tool_event_require_kv_present "$OK_LINE" bundle_id "FAIL:CLI_BUNDLE_ID"
tool_event_require_kv_present "$OK_LINE" manifest_sha256 "FAIL:CLI_MANIFEST_SHA"
tool_event_require_contains "$(tool_event_kv_field "$OK_LINE" bundle_id || true)" "teb_" "FAIL:CLI_BUNDLE_ID_PREFIX"

INVALID_DIR="$(python3 scripts/attest/verify_tool_event_bundle.py --bundle-dir ../bad || true)"
tool_event_require_status_line "$INVALID_DIR" "TOOL_EVENT_BUNDLE_VERIFY " "FAIL:BUNDLE_DIR_INVALID_REASON" \
  ok=no reason=BUNDLE_DIR_INVALID bundle_version=NONE bundle_id=NONE manifest_sha256=NONE files_checked=0 tool_event_digests_count=0

MISSING_DIR="$(python3 scripts/attest/verify_tool_event_bundle.py --bundle-dir out/does_not_exist_tool_event_bundle || true)"
tool_event_require_status_line "$MISSING_DIR" "TOOL_EVENT_BUNDLE_VERIFY " "FAIL:MISSING_DIR_REASON" \
  ok=no reason=BUNDLE_DIR_INVALID bundle_version=NONE bundle_id=NONE manifest_sha256=NONE files_checked=0 tool_event_digests_count=0

python3 - <<'PY'
import json
from pathlib import Path

manifest_path = Path("out/test_verify_tool_event_bundle/BUNDLE_OK/tool_event_bundle.manifest.json")
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
manifest["tool_event_digests"] = ["sha256:" + ("1" * 64)]
manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY

MAP_MISMATCH="$(python3 scripts/attest/verify_tool_event_bundle.py --bundle-dir out/test_verify_tool_event_bundle/BUNDLE_OK || true)"
tool_event_require_status_line "$MAP_MISMATCH" "TOOL_EVENT_BUNDLE_VERIFY " "FAIL:MAP_MISMATCH_REASON" \
  ok=no reason=FILE_DIGEST_MAP_MISMATCH bundle_version=tool_event_bundle_v0 tool_event_digests_count=1
tool_event_require_kv_present "$MAP_MISMATCH" bundle_id "FAIL:MAP_MISMATCH_BUNDLE_ID"
tool_event_require_kv_present "$MAP_MISMATCH" manifest_sha256 "FAIL:MAP_MISMATCH_MANIFEST_SHA"

echo "VERIFY_TOOL_EVENT_BUNDLE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
