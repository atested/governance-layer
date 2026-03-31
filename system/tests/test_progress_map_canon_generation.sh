#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GEN="$ROOT/scripts/dev_generate_progress_map.py"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/progress-map-canon.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

# Create minimal fixtures (no reliance on pre-existing out/)
FIXTURE_DIR="$TMPDIR_LOCAL/fixtures"
mkdir -p "$FIXTURE_DIR"

# Minimal PROGRESS_MAP__DRAFT.md with Phase 2 table
cat > "$FIXTURE_DIR/PROGRESS_MAP__DRAFT.md" <<'DRAFT_EOF'
# PROGRESS MAP (DRAFT v0 - test fixture)

## Phase 2 deliverables/objectives map (initial)

| Item | Plan Source | Evidence anchors | Verification command(s) | Current reading |
|---|---|---|---|---|
| Obj1: test item | PLANNING Phase 2 | test anchor | test command | NOT_EVALUATED |

DRAFT_EOF

# Minimal COMPLETENESS_SNAPSHOT.md with Phase 3 and Phase 4 objectives
cat > "$FIXTURE_DIR/COMPLETENESS_SNAPSHOT.md" <<'SNAPSHOT_EOF'
# Completeness Snapshot (test fixture)

### Phase 3 objectives
1. Test Phase 3 objective one

### Phase 4 objectives
1. Test Phase 4 objective one

SNAPSHOT_EOF

OUT1="$TMPDIR_LOCAL/progress1.json"
OUT2="$TMPDIR_LOCAL/progress2.json"

python3 "$GEN" \
  --progress-map-draft "$FIXTURE_DIR/PROGRESS_MAP__DRAFT.md" \
  --completeness-snapshot "$FIXTURE_DIR/COMPLETENESS_SNAPSHOT.md" \
  --output "$OUT1" >/dev/null

python3 "$GEN" \
  --progress-map-draft "$FIXTURE_DIR/PROGRESS_MAP__DRAFT.md" \
  --completeness-snapshot "$FIXTURE_DIR/COMPLETENESS_SNAPSHOT.md" \
  --output "$OUT2" >/dev/null

H1="$(shasum -a 256 "$OUT1" | awk '{print $1}')"
H2="$(shasum -a 256 "$OUT2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

python3 - "$OUT1" <<'PY'
import json, sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
assert obj.get('version') == 'progress_map_v1'
assert isinstance(obj.get('items'), list)
assert len(obj['items']) > 0
for item in obj['items']:
    assert 'id' in item and item['id']
    assert 'title' in item and item['title']
    assert 'status' in item and item['status']
print('CASE=PROGRESS_MAP_CANON_GENERATION PASS')
PY

echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
