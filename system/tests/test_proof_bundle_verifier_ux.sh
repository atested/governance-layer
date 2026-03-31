#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

set +e
out_fail="$($repo_root/system/tools/proof_bundle_verifier_ux.sh 7 docs/dev/evidence/missing 'Run release-gate and regenerate proof bundle' 2>&1)"
rc_fail=$?
set -e
[[ "$rc_fail" -eq 7 ]]
echo "$out_fail" | rg '^VERIFIER_FAIL$' >/dev/null
echo "$out_fail" | rg '^EXIT_CODE=7$' >/dev/null
echo "$out_fail" | rg '^FAILED_PATH=docs/dev/evidence/missing$' >/dev/null
echo "$out_fail" | rg '^HINT=Run release-gate and regenerate proof bundle$' >/dev/null

out_ok="$($repo_root/system/tools/proof_bundle_verifier_ux.sh 0 docs/dev/evidence/missing 'unused' 2>&1)"
echo "$out_ok" | rg '^VERIFIER_OK$' >/dev/null
echo "$out_ok" | rg '^EXIT_CODE=0$' >/dev/null

echo "TEST_PROOF_BUNDLE_VERIFIER_UX:PASS"
