#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/attest_contract_common.sh"
attest_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_diff_manifest"
attest_reset_work_dir "$TMP_ROOT"

cat > "$TMP_ROOT/left.json" <<'JSON'
{"a":1,"b":{"k":"v"},"c":[1,2]}
JSON
cat > "$TMP_ROOT/right.json" <<'JSON'
{"a":1,"b":{"k":"z"},"c":[1,2,3],"d":true}
JSON

OUT="$(python3 scripts/attest/diff_manifest.py --left "$TMP_ROOT/left.json" --right "$TMP_ROOT/right.json")"
python3 - "$OUT" <<'PY'
import json
import sys
obj = json.loads(sys.argv[1])
assert obj["ok"] is True
assert obj["kind"] == "manifest_diff_v1"
added = {x["path"] for x in obj["added"]}
removed = {x["path"] for x in obj["removed"]}
changed = {x["path"] for x in obj["changed"]}
assert "/d" in added
assert "/c/2" in added
assert "/b/k" in changed
assert not removed
PY

cat > "$TMP_ROOT/bad.json" <<'TXT'
{not-json
TXT
set +e
BAD_OUT="$(python3 scripts/attest/diff_manifest.py --left "$TMP_ROOT/left.json" --right "$TMP_ROOT/bad.json")"
BAD_RC=$?
set -e
[[ $BAD_RC -ne 0 ]] || { echo "FAIL:BAD_SHOULD_FAIL"; exit 1; }
python3 - "$BAD_OUT" <<'PY'
import json
import sys
obj = json.loads(sys.argv[1])
assert obj["ok"] is False
assert obj["kind"] == "manifest_diff_v1"
assert obj["reason"] == "MANIFEST_INVALID"
PY

echo "DIFF_MANIFEST=PASS"
