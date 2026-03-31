#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_event_contract_common.sh"
tool_event_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_export_tool_event_bundle"
OUT_DIR="out/test_export_tool_event_bundle_out"
RUNTIME_DIR="$TMP_ROOT/runtime"
rm -rf "$TMP_ROOT" "$OUT_DIR" out/mcp_exec out/mcp_ingest_tool_event
mkdir -p "$TMP_ROOT" "$OUT_DIR"

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
    return json.loads(proc.stdout.strip())["result"]


params_digest = "sha256:" + hashlib.sha256(b"tool-bundle-params").hexdigest()
out_digest = "sha256:" + hashlib.sha256(b"tool-bundle-output").hexdigest()
req = {
    "id": "INGEST_FOR_BUNDLE",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "INGEST_TOOL_EVENT",
            "params": {
                "tool_event_version": "v0",
                "tool_name": "TEST_TOOL_BUNDLE",
                "tool_params_digest": params_digest,
                "exit_code": 0,
                "outputs": [{"name": "stdout", "digest": out_digest, "ref_type": "blob"}],
                "provenance": {"source_identifier": "TEST_SRC", "extraction_date": "2026-03-06"},
                "policy_context_used": "DEFAULT",
            },
        },
        "mode": {"require_admissible": True, "dry_run": False, "run_id": "RID_TOOL_EVENT_BUNDLE"},
    },
}
res = rpc(req)
if res.get("executed") is not True:
    raise SystemExit("FAIL:INGEST_FAILED")
digest = str(res["ingest_result"]["tool_event_sha256"])

bundle_dir = root / "out/test_export_tool_event_bundle/BUNDLE_A"
proc = subprocess.run(
    [
        "python3",
        str(root / "scripts/attest/export_tool_event_bundle.py"),
        "--digest",
        digest,
        "--out-dir",
        "out/test_export_tool_event_bundle/BUNDLE_A",
    ],
    text=True,
    capture_output=True,
    check=False,
)
if proc.returncode != 0:
    raise SystemExit("FAIL:EXPORT_FAILED")
lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
if len(lines) != 1:
    raise SystemExit("FAIL:EXPORT_CONTRACT_LINES")
line = lines[0]
if "TOOL_EVENT_BUNDLE_EXPORT ok=yes reason=OK " not in line:
    raise SystemExit("FAIL:EXPORT_CONTRACT_PREFIX")
tokens = {}
for part in line.split():
    if "=" in part:
        k, v = part.split("=", 1)
        tokens[k] = v
if not str(tokens.get("bundle_id", "")).startswith("teb_"):
    raise SystemExit("FAIL:EXPORT_BUNDLE_ID")
if not str(tokens.get("manifest_sha256", "")).startswith("sha256:"):
    raise SystemExit("FAIL:EXPORT_MANIFEST_SHA")
if str(tokens.get("bundle_version", "")) != "tool_event_bundle_v0":
    raise SystemExit("FAIL:EXPORT_BUNDLE_VERSION")
if int(tokens.get("tool_event_digests_count", "0")) != 1:
    raise SystemExit("FAIL:EXPORT_DIGEST_COUNT")

manifest_path = bundle_dir / "tool_event_bundle.manifest.json"
if not manifest_path.is_file():
    raise SystemExit("FAIL:MANIFEST_MISSING")
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("bundle_version") != "tool_event_bundle_v0":
    raise SystemExit("FAIL:BUNDLE_VERSION")
if manifest.get("tool_event_digests") != [digest]:
    raise SystemExit("FAIL:DIGEST_LIST")

files = manifest.get("files", {})
if not isinstance(files, dict) or len(files) != 1:
    raise SystemExit("FAIL:FILES_MAP")
rel_path = next(iter(files.keys()))
payload = (bundle_dir / rel_path).read_bytes()
got = "sha256:" + hashlib.sha256(payload).hexdigest()
if got != files[rel_path].get("sha256"):
    raise SystemExit("FAIL:PAYLOAD_HASH")
if len(payload) != int(files[rel_path].get("size_bytes", -1)):
    raise SystemExit("FAIL:PAYLOAD_SIZE")

summary = {
    "digest": digest,
    "manifest_sha256": "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    "payload_sha256": got,
    "payload_rel": rel_path,
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$OUT_DIR/run1.json"
R2="$OUT_DIR/run2.json"
run_once "$R1"
run_once "$R2"

_HASHES="$(tool_event_require_deterministic_files "$R1" "$R2" "FAIL:NON_DETERMINISTIC")"
H1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
H2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"

NEG="$(python3 scripts/attest/export_tool_event_bundle.py --digest "sha256:$(printf '0%.0s' {1..64})" --out-dir out/test_export_tool_event_bundle/EMPTY_NEG || true)"
tool_event_require_status_line "$NEG" "TOOL_EVENT_BUNDLE_EXPORT " "FAIL:NEGATIVE_CONTRACT" \
  ok=no reason=TOOL_EVENT_NOT_FOUND bundle_version=NONE bundle_id=NONE manifest_sha256=NONE tool_event_digests_count=0

BAD_DIGEST="$(python3 scripts/attest/export_tool_event_bundle.py --digest not_a_digest --out-dir out/test_export_tool_event_bundle/BAD_DIGEST || true)"
tool_event_require_status_line "$BAD_DIGEST" "TOOL_EVENT_BUNDLE_EXPORT " "FAIL:BAD_DIGEST_REASON" \
  ok=no reason=DIGEST_INVALID bundle_id=NONE manifest_sha256=NONE bundle_version=NONE tool_event_digests_count=0

BAD_RECEIPT="$(python3 scripts/attest/export_tool_event_bundle.py --receipt-id 'bad receipt id' --out-dir out/test_export_tool_event_bundle/BAD_RECEIPT || true)"
tool_event_require_status_line "$BAD_RECEIPT" "TOOL_EVENT_BUNDLE_EXPORT " "FAIL:BAD_RECEIPT_REASON" \
  ok=no reason=RECEIPT_ID_INVALID bundle_id=NONE manifest_sha256=NONE bundle_version=NONE tool_event_digests_count=0

BAD_OUT_DIR="$(python3 scripts/attest/export_tool_event_bundle.py --digest "sha256:$(printf '0%.0s' {1..64})" --out-dir ../bad_out || true)"
tool_event_require_status_line "$BAD_OUT_DIR" "TOOL_EVENT_BUNDLE_EXPORT " "FAIL:BAD_OUT_DIR_REASON" \
  ok=no reason=OUT_DIR_INVALID bundle_id=NONE manifest_sha256=NONE bundle_version=NONE tool_event_digests_count=0

echo "EXPORT_TOOL_EVENT_BUNDLE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
