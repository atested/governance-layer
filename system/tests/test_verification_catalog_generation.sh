#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/vcat-gen.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

IN_MD="$TMPDIR_LOCAL/catalog.md"
OUT1="$TMPDIR_LOCAL/catalog1.json"
OUT2="$TMPDIR_LOCAL/catalog2.json"

cat > "$IN_MD" <<'EOF'
# Verification Catalog

## system/tests (shell)
```
system/tests/test_no_conflict_markers_tracked.sh
system/tests/test_no_absolute_paths_tracked.sh
```

## scripts (top-level)
```
scripts/policy-eval.py
```
EOF

python3 "$ROOT/scripts/dev_generate_verification_catalog.py" --input "$IN_MD" --output "$OUT1" >/dev/null
python3 "$ROOT/scripts/dev_generate_verification_catalog.py" --input "$IN_MD" --output "$OUT2" >/dev/null

S1="$(shasum -a 256 "$OUT1" | awk '{print $1}')"
S2="$(shasum -a 256 "$OUT2" | awk '{print $1}')"
[[ "$S1" == "$S2" ]] || { echo "FAIL: nondeterministic catalog output"; exit 1; }

python3 - "$OUT1" <<'PY'
import json
import sys
j=json.load(open(sys.argv[1],encoding='utf-8'))
assert j['entry_count'] >= 3
for e in j['entries']:
    for k in ('id','title','objective','verification_cmd','description'):
        assert k in e
print('CASE=VERIFICATION_CATALOG_GENERATION PASS')
PY

echo "RUN1_SHA256=$S1"
echo "RUN2_SHA256=$S2"
