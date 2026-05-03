#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_DIR="out/test_mcp_reference_workflow_e2e"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

R1="$TMP_DIR/run1.txt"
R2="$TMP_DIR/run2.txt"

bash scripts/dev_mcp_reference_workflow.sh > "$R1"
bash scripts/dev_mcp_reference_workflow.sh > "$R2"

H1="$(shasum -a 256 "$R1" | awk '{print $1}')"
H2="$(shasum -a 256 "$R2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

for token in \
  MCP_LIST_OK \
  MCP_DESCRIBE_OK \
  MCP_NORMALIZE_OK \
  MCP_PREFLIGHT_DEFAULT_OK \
  MCP_PREFLIGHT_STRICT_OUT_ONLY_NO \
  MCP_EXEC_ATTESTED_OK \
  BUNDLE_VERIFY_OK \
  RECEIPT_OK \
  REPLAY_DEFAULT_OK \
  REPLAY_STRICT_OUT_ONLY_NO
 do
  rg -n "^${token}$" "$R1" >/dev/null || { echo "FAIL:MISSING_TOKEN:${token}"; exit 1; }
 done

echo "MCP_REFERENCE_WORKFLOW_E2E=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
