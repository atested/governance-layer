#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_admissibility_policy_context_drift"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT/fixtures"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT/fixtures"
  mkdir -p "$TMP_ROOT/fixtures"
  printf 'drift\n' > "$TMP_ROOT/fixtures/src.txt"

  python3 - "$ROOT" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])

req_default = {
    "id": "CTX_A",
    "method": "capabilities.admissibility_check",
    "params": {
        "capabilities_version": "v0",
        "policy_context": "DEFAULT",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_mcp_admissibility_policy_context_drift/fixtures/src.txt",
                "dst_path": "out/test_mcp_admissibility_policy_context_drift/fixtures/dst.txt",
                "overwrite": False,
            },
        },
    },
}
req_strict = {
    "id": "CTX_B",
    "method": "capabilities.admissibility_check",
    "params": {
        "capabilities_version": "v0",
        "policy_context": "STRICT_OUT_ONLY",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_mcp_admissibility_policy_context_drift/fixtures/src.txt",
                "dst_path": "out/test_mcp_admissibility_policy_context_drift/fixtures/dst.txt",
                "overwrite": False,
            },
        },
    },
}

def call(req):
    proc = subprocess.run(
        ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
        input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("FAIL:REQUEST_RC")
    return json.loads(proc.stdout.strip())["result"]

res_default = call(req_default)
res_strict = call(req_strict)

if res_default.get("admissible") is not True:
    raise SystemExit("FAIL:DEFAULT_NOT_ADMISSIBLE")
if res_default.get("reason_token") != "NONE":
    raise SystemExit("FAIL:DEFAULT_REASON")
if res_default.get("policy_context_used") != "DEFAULT":
    raise SystemExit("FAIL:DEFAULT_CONTEXT")

if res_strict.get("admissible") is not False:
    raise SystemExit("FAIL:STRICT_NOT_BLOCKED")
if res_strict.get("reason_token") != "OUTSIDE_ALLOWED_ROOT":
    raise SystemExit("FAIL:STRICT_REASON")
if res_strict.get("policy_context_used") != "STRICT_OUT_ONLY":
    raise SystemExit("FAIL:STRICT_CONTEXT")

out = {
    "default": {
        "admissible": res_default.get("admissible"),
        "reason_token": res_default.get("reason_token"),
        "policy_context_used": res_default.get("policy_context_used"),
    },
    "strict": {
        "admissible": res_strict.get("admissible"),
        "reason_token": res_strict.get("reason_token"),
        "policy_context_used": res_strict.get("policy_context_used"),
    },
}
out_file.write_text(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

RUN1="$TMP_ROOT/run1.json"
RUN2="$TMP_ROOT/run2.json"
run_once "$RUN1"
run_once "$RUN2"

H1="$(shasum -a 256 "$RUN1" | awk '{print $1}')"
H2="$(shasum -a 256 "$RUN2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_ADMISSIBILITY_POLICY_CONTEXT_DRIFT=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
