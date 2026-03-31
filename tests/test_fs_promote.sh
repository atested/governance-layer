#!/usr/bin/env bash
# test_fs_promote.sh — Policy + integrity tests for FS_PROMOTE governed tool.
#
# T-PROMO-001: deny direct FS_MOVE cross-root attempt (invariant preservation)
# T-PROMO-002: deny FS_PROMOTE when root pair is not explicitly allowed
# T-PROMO-003: deny when source hash does not match declared hash
# T-PROMO-004: deny hidden/traversal source path
# T-PROMO-005: allow valid promotion with matching source hash and full records
# T-PROMO-006: valid record passes verify-record (integrity fail-closed)
# T-PROMO-007: deny unapproved artifact class
# T-PROMO-008: deny overwrite when policy disallows overwrite
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
VERIFY="$ROOT/scripts/verify-record.py"
REPLAY="$ROOT/scripts/replay-record.py"
FIXTURES="$ROOT/tests/fixtures"

TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/test-fs-promote.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

export GOV_CANONICAL_REPO_PATH="$ROOT"
export GOV_RUNTIME_PATH="$TMPDIR_LOCAL/runtime"
mkdir -p "$GOV_RUNTIME_PATH" "$ROOT/LOGS"

pass=0
fail=0

assert_contains () {
  local name="$1" json="$2" expect="$3"
  if echo "$json" | grep -q "$expect"; then
    echo "PASS: $name (contains $expect)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (missing $expect)"
    echo "$json"
    fail=$((fail+1))
  fi
}

assert_not_contains () {
  local name="$1" json="$2" absent="$3"
  if echo "$json" | grep -q "$absent"; then
    echo "FAIL: $name (should not contain $absent)"
    fail=$((fail+1))
  else
    echo "PASS: $name (correctly absent: $absent)"
    pass=$((pass+1))
  fi
}

verify_hash () {
  local name="$1" json_file="$2"
  if "$VERIFY" "$json_file" >/dev/null 2>&1; then
    echo "PASS: $name (record_hash verified)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (record_hash verify failed)"
    "$VERIFY" "$json_file" || true
    fail=$((fail+1))
  fi
}

replay_check () {
  local name="$1" json_file="$2"
  local rc=0
  local out
  out="$(python3 "$REPLAY" "$json_file" 2>&1)" || rc=$?
  if [[ $rc -eq 0 ]]; then
    echo "PASS: $name (replay exit 0)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (replay exit $rc)"
    echo "$out"
    fail=$((fail+1))
  fi
}

# ---------------------------------------------------------------------------
# T-PROMO-001: FS_MOVE cross-root attempt is denied (INV-PROMO-001)
# Use dynamic paths so src and dst are in different resolved roots.
# ---------------------------------------------------------------------------
echo "--- T-PROMO-001: FS_MOVE cross-root denied (invariant preservation) ---"

FIXTURE1="$TMPDIR_LOCAL/move_deny_cross_root.json"
cat > "$FIXTURE1" <<EOF
{
  "tool": "FS_MOVE",
  "args": {
    "src_path": "$GOV_RUNTIME_PATH/move-src-001.txt",
    "dst_path": "$ROOT/LOGS/move-dst-001.txt",
    "overwrite": false
  },
  "intent": {
    "goal": "Attempt cross-root move from runtime root to canonical repo root.",
    "constraints": {"overwrite": false},
    "requested_action": "FS_MOVE",
    "inputs": [{"ref": "file:src_path", "value": "$GOV_RUNTIME_PATH/move-src-001.txt"}],
    "expected_outputs": [{"ref": "file:dst_path", "value": "$ROOT/LOGS/move-dst-001.txt"}]
  }
}
EOF

j1="$(python3 "$EVAL" "$FIXTURE1")"
echo "$j1" > "$ROOT/LOGS/t-promo-001.record.json"

assert_contains     "T-PROMO-001 decision DENY"            "$j1" '"policy_decision": "DENY"'
assert_contains     "T-PROMO-001 reason CROSS-ROOT"        "$j1" 'RC-FS-CROSS-ROOT-DISALLOWED'
assert_not_contains "T-PROMO-001 no ALLOW"                 "$j1" '"policy_decision": "ALLOW"'
verify_hash         "T-PROMO-001 verify-record"            "$ROOT/LOGS/t-promo-001.record.json"
replay_check        "T-PROMO-001 replay"                   "$ROOT/LOGS/t-promo-001.record.json"

echo
# ---------------------------------------------------------------------------
# T-PROMO-002: deny FS_PROMOTE when root pair is not in allowlist
# ---------------------------------------------------------------------------
echo "--- T-PROMO-002: deny FS_PROMOTE with disallowed root pair ---"

SRC2="$GOV_RUNTIME_PATH/promo-src-002.txt"
DST2="$TMPDIR_LOCAL/canonical/promo-dst-002.txt"
echo "promo-content-002" > "$SRC2"
HASH2="sha256:$(python3 -c "import hashlib; print(hashlib.sha256(open('$SRC2','rb').read()).hexdigest())")"
mkdir -p "$(dirname "$DST2")"

FIXTURE2="$TMPDIR_LOCAL/promo_deny_root_pair.json"
cat > "$FIXTURE2" <<EOF
{
  "tool": "FS_PROMOTE",
  "args": {"src_path": "$SRC2", "dst_path": "$DST2"},
  "intent": {
    "goal": "Attempt promotion with disallowed root pair.",
    "expected_outputs": [{"ref": "file:dst_path", "value": "$DST2"}],
    "promotion_id": "promo-test-002",
    "src_root_id": "runtime",
    "dst_root_id": "disallowed_root",
    "src_content_hash_sha256": "$HASH2",
    "allowed_artifact_class": "vetted_output",
    "requested_by": "test-actor"
  }
}
EOF

j2="$(python3 "$EVAL" "$FIXTURE2")"
echo "$j2" > "$ROOT/LOGS/t-promo-002.record.json"

assert_contains     "T-PROMO-002 decision DENY"               "$j2" '"policy_decision": "DENY"'
assert_contains     "T-PROMO-002 reason ROOT-PAIR-DISALLOWED" "$j2" 'RC-PROMO-ROOT-PAIR-DISALLOWED'
assert_not_contains "T-PROMO-002 no ALLOW"                    "$j2" '"policy_decision": "ALLOW"'
verify_hash         "T-PROMO-002 verify-record"               "$ROOT/LOGS/t-promo-002.record.json"
replay_check        "T-PROMO-002 replay"                      "$ROOT/LOGS/t-promo-002.record.json"

echo
# ---------------------------------------------------------------------------
# T-PROMO-003: deny when source hash does not match declared hash
# ---------------------------------------------------------------------------
echo "--- T-PROMO-003: deny FS_PROMOTE source hash mismatch ---"

SRC3="$GOV_RUNTIME_PATH/promo-src-003.txt"
DST3="$ROOT/LOGS/promo-dst-003.txt"
echo "promo-content-003" > "$SRC3"

FIXTURE3="$TMPDIR_LOCAL/promo_deny_hash_mismatch.json"
cat > "$FIXTURE3" <<EOF
{
  "tool": "FS_PROMOTE",
  "args": {"src_path": "$SRC3", "dst_path": "$DST3"},
  "intent": {
    "goal": "Attempt promotion with wrong declared hash.",
    "expected_outputs": [{"ref": "file:dst_path", "value": "$DST3"}],
    "promotion_id": "promo-test-003",
    "src_root_id": "runtime",
    "dst_root_id": "canonical_repo",
    "src_content_hash_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "allowed_artifact_class": "vetted_output",
    "requested_by": "test-actor"
  }
}
EOF

j3="$(python3 "$EVAL" "$FIXTURE3")"
echo "$j3" > "$ROOT/LOGS/t-promo-003.record.json"

assert_contains     "T-PROMO-003 decision DENY"              "$j3" '"policy_decision": "DENY"'
assert_contains     "T-PROMO-003 reason HASH-MISMATCH-SRC"   "$j3" 'RC-PROMO-HASH-MISMATCH-SRC'
assert_not_contains "T-PROMO-003 no ALLOW"                   "$j3" '"policy_decision": "ALLOW"'
verify_hash         "T-PROMO-003 verify-record"              "$ROOT/LOGS/t-promo-003.record.json"
replay_check        "T-PROMO-003 replay"                     "$ROOT/LOGS/t-promo-003.record.json"

echo
# ---------------------------------------------------------------------------
# T-PROMO-004: deny hidden/traversal paths
# ---------------------------------------------------------------------------
echo "--- T-PROMO-004: deny hidden/traversal source path ---"

DST4="$ROOT/LOGS/promo-dst-004.txt"

FIXTURE4="$TMPDIR_LOCAL/promo_deny_hidden.json"
cat > "$FIXTURE4" <<EOF
{
  "tool": "FS_PROMOTE",
  "args": {"src_path": "$GOV_RUNTIME_PATH/.hidden/secret.txt", "dst_path": "$DST4"},
  "intent": {
    "goal": "Attempt promotion from hidden path.",
    "expected_outputs": [{"ref": "file:dst_path", "value": "$DST4"}],
    "promotion_id": "promo-test-004",
    "src_root_id": "runtime",
    "dst_root_id": "canonical_repo",
    "src_content_hash_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "allowed_artifact_class": "vetted_output",
    "requested_by": "test-actor"
  }
}
EOF

j4="$(python3 "$EVAL" "$FIXTURE4")"
echo "$j4" > "$ROOT/LOGS/t-promo-004.record.json"

assert_contains     "T-PROMO-004 decision DENY"         "$j4" '"policy_decision": "DENY"'
assert_contains     "T-PROMO-004 reason hidden path"    "$j4" 'RC-FS-HIDDEN-PATH'
assert_contains     "T-PROMO-004 reason SRC-MISSING"    "$j4" 'RC-PROMO-SRC-MISSING'
assert_not_contains "T-PROMO-004 no ALLOW"              "$j4" '"policy_decision": "ALLOW"'
verify_hash         "T-PROMO-004 verify-record"         "$ROOT/LOGS/t-promo-004.record.json"
replay_check        "T-PROMO-004 replay"                "$ROOT/LOGS/t-promo-004.record.json"

echo
# ---------------------------------------------------------------------------
# T-PROMO-005: allow valid promotion with matching hash and full intent
# ---------------------------------------------------------------------------
echo "--- T-PROMO-005: allow valid promotion with matching hash ---"

SRC5="$GOV_RUNTIME_PATH/promo-src-005.txt"
DST5="$ROOT/LOGS/promo-dst-005.txt"
echo "promo-content-005" > "$SRC5"
HASH5="sha256:$(python3 -c "import hashlib; print(hashlib.sha256(open('$SRC5','rb').read()).hexdigest())")"

FIXTURE5="$TMPDIR_LOCAL/promo_allow.json"
cat > "$FIXTURE5" <<EOF
{
  "tool": "FS_PROMOTE",
  "args": {"src_path": "$SRC5", "dst_path": "$DST5"},
  "intent": {
    "goal": "Promote vetted output from runtime to canonical repo.",
    "expected_outputs": [{"ref": "file:dst_path", "value": "$DST5"}],
    "promotion_id": "promo-test-005",
    "src_root_id": "runtime",
    "dst_root_id": "canonical_repo",
    "src_content_hash_sha256": "$HASH5",
    "allowed_artifact_class": "vetted_output",
    "requested_by": "test-actor"
  }
}
EOF

j5="$(python3 "$EVAL" "$FIXTURE5")"
echo "$j5" > "$ROOT/LOGS/t-promo-005.record.json"

assert_contains     "T-PROMO-005 decision ALLOW"             "$j5" '"policy_decision": "ALLOW"'
assert_contains     "T-PROMO-005 tool FS_PROMOTE"            "$j5" '"tool": "FS_PROMOTE"'
assert_contains     "T-PROMO-005 canonical_src_path"         "$j5" '"canonical_src_path"'
assert_contains     "T-PROMO-005 canonical_dst_path"         "$j5" '"canonical_dst_path"'
assert_contains     "T-PROMO-005 promotion_id"               "$j5" '"promotion_id"'
assert_contains     "T-PROMO-005 cap_registry_hash"          "$j5" '"cap_registry_hash": "sha256:'
assert_contains     "T-PROMO-005 request_hash"               "$j5" '"request_hash": "sha256:'
assert_not_contains "T-PROMO-005 no policy_reasons"          "$j5" 'RC-PROMO'
verify_hash         "T-PROMO-005 verify-record"              "$ROOT/LOGS/t-promo-005.record.json"
replay_check        "T-PROMO-005 replay"                     "$ROOT/LOGS/t-promo-005.record.json"

echo
# ---------------------------------------------------------------------------
# T-PROMO-006: valid record passes verify-record (integrity fail-closed)
# ---------------------------------------------------------------------------
echo "--- T-PROMO-006: FS_PROMOTE record integrity verified by verify-record ---"

# Reuse the ALLOW record from T-PROMO-005 for integrity check
if "$VERIFY" "$ROOT/LOGS/t-promo-005.record.json" >/dev/null 2>&1; then
  echo "PASS: T-PROMO-006 FS_PROMOTE record passes verify-record hash check"
  pass=$((pass+1))
else
  echo "FAIL: T-PROMO-006 FS_PROMOTE record failed verify-record hash check"
  fail=$((fail+1))
fi

echo
# ---------------------------------------------------------------------------
# T-PROMO-007: deny unapproved artifact class
# ---------------------------------------------------------------------------
echo "--- T-PROMO-007: deny FS_PROMOTE with unapproved artifact class ---"

SRC7="$GOV_RUNTIME_PATH/promo-src-007.txt"
DST7="$ROOT/LOGS/promo-dst-007.txt"
echo "promo-content-007" > "$SRC7"
HASH7="sha256:$(python3 -c "import hashlib; print(hashlib.sha256(open('$SRC7','rb').read()).hexdigest())")"

FIXTURE7="$TMPDIR_LOCAL/promo_deny_artifact_class.json"
cat > "$FIXTURE7" <<EOF
{
  "tool": "FS_PROMOTE",
  "args": {"src_path": "$SRC7", "dst_path": "$DST7"},
  "intent": {
    "goal": "Attempt promotion with unapproved artifact class.",
    "expected_outputs": [{"ref": "file:dst_path", "value": "$DST7"}],
    "promotion_id": "promo-test-007",
    "src_root_id": "runtime",
    "dst_root_id": "canonical_repo",
    "src_content_hash_sha256": "$HASH7",
    "allowed_artifact_class": "unapproved_class",
    "requested_by": "test-actor"
  }
}
EOF

j7="$(python3 "$EVAL" "$FIXTURE7")"
echo "$j7" > "$ROOT/LOGS/t-promo-007.record.json"

assert_contains     "T-PROMO-007 decision DENY"                    "$j7" '"policy_decision": "DENY"'
assert_contains     "T-PROMO-007 reason ARTIFACT-CLASS-DISALLOWED" "$j7" 'RC-PROMO-ARTIFACT-CLASS-DISALLOWED'
assert_not_contains "T-PROMO-007 no ALLOW"                         "$j7" '"policy_decision": "ALLOW"'
verify_hash         "T-PROMO-007 verify-record"                    "$ROOT/LOGS/t-promo-007.record.json"
replay_check        "T-PROMO-007 replay"                           "$ROOT/LOGS/t-promo-007.record.json"

echo
# ---------------------------------------------------------------------------
# T-PROMO-008: deny overwrite when destination exists and overwrite_allowed=false
# ---------------------------------------------------------------------------
echo "--- T-PROMO-008: deny FS_PROMOTE overwrite when policy disallows ---"

SRC8="$GOV_RUNTIME_PATH/promo-src-008.txt"
DST8="$ROOT/LOGS/promo-dst-008.txt"
echo "promo-content-008" > "$SRC8"
echo "existing-content" > "$DST8"
HASH8="sha256:$(python3 -c "import hashlib; print(hashlib.sha256(open('$SRC8','rb').read()).hexdigest())")"

FIXTURE8="$TMPDIR_LOCAL/promo_deny_overwrite.json"
cat > "$FIXTURE8" <<EOF
{
  "tool": "FS_PROMOTE",
  "args": {"src_path": "$SRC8", "dst_path": "$DST8"},
  "intent": {
    "goal": "Attempt promotion to existing destination without overwrite.",
    "expected_outputs": [{"ref": "file:dst_path", "value": "$DST8"}],
    "promotion_id": "promo-test-008",
    "src_root_id": "runtime",
    "dst_root_id": "canonical_repo",
    "src_content_hash_sha256": "$HASH8",
    "allowed_artifact_class": "vetted_output",
    "requested_by": "test-actor"
  }
}
EOF

j8="$(python3 "$EVAL" "$FIXTURE8")"
echo "$j8" > "$ROOT/LOGS/t-promo-008.record.json"

assert_contains     "T-PROMO-008 decision DENY"              "$j8" '"policy_decision": "DENY"'
assert_contains     "T-PROMO-008 reason OVERWRITE-DISALLOWED" "$j8" 'RC-PROMO-OVERWRITE-DISALLOWED'
assert_not_contains "T-PROMO-008 no ALLOW"                   "$j8" '"policy_decision": "ALLOW"'
verify_hash         "T-PROMO-008 verify-record"              "$ROOT/LOGS/t-promo-008.record.json"
replay_check        "T-PROMO-008 replay"                     "$ROOT/LOGS/t-promo-008.record.json"

echo
# ---------------------------------------------------------------------------
# T-PROMO-009: deny when src_path is not under the declared src_root_id base
# ---------------------------------------------------------------------------
echo "--- T-PROMO-009: deny FS_PROMOTE src_path not under declared src_root_id ---"

# src declared as "runtime" but actually points into canonical_repo root
DST9="$ROOT/LOGS/promo-dst-009.txt"
FIXTURE9="$TMPDIR_LOCAL/promo_deny_path_disallowed.json"
cat > "$FIXTURE9" <<EOF
{
  "tool": "FS_PROMOTE",
  "args": {"src_path": "$ROOT/LOGS/some-source.txt", "dst_path": "$DST9"},
  "intent": {
    "goal": "Attempt promotion where src_path is not under declared src_root_id.",
    "expected_outputs": [{"ref": "file:dst_path", "value": "$DST9"}],
    "promotion_id": "promo-test-009",
    "src_root_id": "runtime",
    "dst_root_id": "canonical_repo",
    "src_content_hash_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "allowed_artifact_class": "vetted_output",
    "requested_by": "test-actor"
  }
}
EOF

j9="$(python3 "$EVAL" "$FIXTURE9")"
echo "$j9" > "$ROOT/LOGS/t-promo-009.record.json"

assert_contains     "T-PROMO-009 decision DENY"           "$j9" '"policy_decision": "DENY"'
assert_contains     "T-PROMO-009 reason PATH-DISALLOWED"  "$j9" 'RC-PROMO-PATH-DISALLOWED'
assert_not_contains "T-PROMO-009 no ALLOW"                "$j9" '"policy_decision": "ALLOW"'
verify_hash         "T-PROMO-009 verify-record"           "$ROOT/LOGS/t-promo-009.record.json"
replay_check        "T-PROMO-009 replay"                  "$ROOT/LOGS/t-promo-009.record.json"

echo
# ---------------------------------------------------------------------------
# T-PROMO-010: deny when source exists but is a directory, not a regular file
# ---------------------------------------------------------------------------
echo "--- T-PROMO-010: deny FS_PROMOTE when source is a directory ---"

SRC10="$GOV_RUNTIME_PATH/promo-src-dir-010"
DST10="$ROOT/LOGS/promo-dst-010.txt"
mkdir -p "$SRC10"

FIXTURE10="$TMPDIR_LOCAL/promo_deny_src_type.json"
cat > "$FIXTURE10" <<EOF
{
  "tool": "FS_PROMOTE",
  "args": {"src_path": "$SRC10", "dst_path": "$DST10"},
  "intent": {
    "goal": "Attempt promotion where source is a directory.",
    "expected_outputs": [{"ref": "file:dst_path", "value": "$DST10"}],
    "promotion_id": "promo-test-010",
    "src_root_id": "runtime",
    "dst_root_id": "canonical_repo",
    "src_content_hash_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "allowed_artifact_class": "vetted_output",
    "requested_by": "test-actor"
  }
}
EOF

j10="$(python3 "$EVAL" "$FIXTURE10")"
echo "$j10" > "$ROOT/LOGS/t-promo-010.record.json"

assert_contains     "T-PROMO-010 decision DENY"                "$j10" '"policy_decision": "DENY"'
assert_contains     "T-PROMO-010 reason SRC-TYPE-DISALLOWED"   "$j10" 'RC-PROMO-SRC-TYPE-DISALLOWED'
assert_not_contains "T-PROMO-010 no ALLOW"                     "$j10" '"policy_decision": "ALLOW"'
verify_hash         "T-PROMO-010 verify-record"                "$ROOT/LOGS/t-promo-010.record.json"
replay_check        "T-PROMO-010 replay"                       "$ROOT/LOGS/t-promo-010.record.json"

echo
# ---------------------------------------------------------------------------
# Execution-layer tests (T408 runtime tranche: EPIC_PROMOTION.md steps 8–10)
# ---------------------------------------------------------------------------
EXEC="$ROOT/scripts/fs-promote-exec.py"

# ---------------------------------------------------------------------------
# T-PROMO-011: successful promotion execution
# Runs policy-eval to get an ALLOW record, then executes fs-promote-exec.
# Verifies: dst file exists, completion record emitted, outcome PROMOTED,
#           INV-PROMO-004 satisfied (dst_hash_verified=true), INV-PROMO-005
#           satisfied (promotion_id + decision_record_hash present).
# ---------------------------------------------------------------------------
echo "--- T-PROMO-011: successful promotion execution ---"

SRC11="$GOV_RUNTIME_PATH/promo-src-011.txt"
DST11="$ROOT/LOGS/promo-dst-011.txt"
rm -f "$DST11"
echo "promo-content-011" > "$SRC11"
HASH11="sha256:$(python3 -c "import hashlib; print(hashlib.sha256(open('$SRC11','rb').read()).hexdigest())")"

FIXTURE11="$TMPDIR_LOCAL/promo_exec_allow.json"
cat > "$FIXTURE11" <<EOF
{
  "tool": "FS_PROMOTE",
  "args": {"src_path": "$SRC11", "dst_path": "$DST11"},
  "intent": {
    "goal": "Promote vetted output from runtime to canonical repo.",
    "expected_outputs": [{"ref": "file:dst_path", "value": "$DST11"}],
    "promotion_id": "promo-exec-011",
    "src_root_id": "runtime",
    "dst_root_id": "canonical_repo",
    "src_content_hash_sha256": "$HASH11",
    "allowed_artifact_class": "vetted_output",
    "requested_by": "test-actor"
  }
}
EOF

j11="$(python3 "$EVAL" "$FIXTURE11")"
echo "$j11" > "$ROOT/LOGS/t-promo-011-decision.record.json"

# Verify policy-eval gave ALLOW before attempting execution
if ! echo "$j11" | grep -q '"policy_decision": "ALLOW"'; then
  echo "FAIL: T-PROMO-011 setup: policy-eval did not return ALLOW"
  echo "$j11"
  fail=$((fail+1))
else
  exec_rc11=0
  exec_out11="$(python3 "$EXEC" "$ROOT/LOGS/t-promo-011-decision.record.json")" || exec_rc11=$?
  echo "$exec_out11" > "$ROOT/LOGS/t-promo-011-completion.record.json"

  if [[ $exec_rc11 -eq 0 ]]; then
    echo "PASS: T-PROMO-011 exec exit 0"
    pass=$((pass+1))
  else
    echo "FAIL: T-PROMO-011 exec exit $exec_rc11"
    echo "$exec_out11"
    fail=$((fail+1))
  fi

  assert_contains     "T-PROMO-011 dst file exists"          "$(test -f "$DST11" && echo ok)" "ok"
  assert_contains     "T-PROMO-011 outcome PROMOTED"         "$exec_out11" '"completion_outcome": "PROMOTED"'
  assert_contains     "T-PROMO-011 dst_hash_verified true"   "$exec_out11" '"dst_hash_verified": true'
  assert_contains     "T-PROMO-011 promotion_id"             "$exec_out11" '"promotion_id": "promo-exec-011"'
  assert_contains     "T-PROMO-011 decision_record_hash"     "$exec_out11" '"decision_record_hash"'
  assert_contains     "T-PROMO-011 dst_content_hash_sha256"  "$exec_out11" '"dst_content_hash_sha256"'
  assert_contains     "T-PROMO-011 src_content_hash_sha256"  "$exec_out11" '"src_content_hash_sha256"'
  assert_contains     "T-PROMO-011 record_type completion"   "$exec_out11" '"record_type": "promotion_completion"'
  assert_contains     "T-PROMO-011 record_hash present"      "$exec_out11" '"record_hash": "sha256:'
  verify_hash         "T-PROMO-011 completion verify-record" "$ROOT/LOGS/t-promo-011-completion.record.json"
fi

echo
# ---------------------------------------------------------------------------
# T-PROMO-012: completion record presence/consistency
# Verify INV-PROMO-005: decision_record_hash in completion record matches the
# ALLOW decision record's record_hash field.
# ---------------------------------------------------------------------------
echo "--- T-PROMO-012: completion record linked to decision record (INV-PROMO-005) ---"

DEC_HASH12="$(python3 -c "import json; d=json.load(open('$ROOT/LOGS/t-promo-011-decision.record.json')); print(d['record_hash'])")"
COMP_DECHASH12="$(python3 -c "import json; d=json.load(open('$ROOT/LOGS/t-promo-011-completion.record.json')); print(d.get('decision_record_hash',''))")"

if [[ "$DEC_HASH12" == "$COMP_DECHASH12" && -n "$DEC_HASH12" ]]; then
  echo "PASS: T-PROMO-012 decision_record_hash matches (INV-PROMO-005 satisfied)"
  pass=$((pass+1))
else
  echo "FAIL: T-PROMO-012 decision_record_hash mismatch: decision=$DEC_HASH12 completion=$COMP_DECHASH12"
  fail=$((fail+1))
fi

# Also verify prev_record_hash equals decision_record_hash for chain linkage.
PREV_HASH12="$(python3 -c "import json; d=json.load(open('$ROOT/LOGS/t-promo-011-completion.record.json')); print(d.get('prev_record_hash',''))")"
if [[ "$PREV_HASH12" == "$DEC_HASH12" ]]; then
  echo "PASS: T-PROMO-012 prev_record_hash == decision_record_hash (chain linked)"
  pass=$((pass+1))
else
  echo "FAIL: T-PROMO-012 prev_record_hash mismatch: expected=$DEC_HASH12 got=$PREV_HASH12"
  fail=$((fail+1))
fi

echo
# ---------------------------------------------------------------------------
# T-PROMO-013: reject DENY decision record (fail-closed, no file copy)
# fs-promote-exec must refuse a DENY record and exit non-zero without
# touching the destination.
# ---------------------------------------------------------------------------
echo "--- T-PROMO-013: reject DENY decision record (fail-closed) ---"

DST13="$ROOT/LOGS/promo-dst-013.txt"
rm -f "$DST13"

# Reuse the DENY record from T-PROMO-003 (source hash mismatch -> DENY).
if python3 "$EXEC" "$ROOT/LOGS/t-promo-003.record.json" >/dev/null 2>&1; then
  echo "FAIL: T-PROMO-013 exec should have rejected DENY record but exited 0"
  fail=$((fail+1))
else
  echo "PASS: T-PROMO-013 exec correctly rejected DENY record (exit non-zero)"
  pass=$((pass+1))
fi

# Destination must not have been created.
assert_contains "T-PROMO-013 dst not created" "$(test ! -f "$DST13" && echo absent)" "absent"

echo
# ---------------------------------------------------------------------------
# T-PROMO-014: reject tampered decision record (chain integrity fail-closed)
# Tamper with a valid ALLOW record's record_hash field; exec must abort with
# exit 2 and not perform any copy.
# ---------------------------------------------------------------------------
echo "--- T-PROMO-014: reject tampered decision record hash (chain verify fail-closed) ---"

SRC14="$GOV_RUNTIME_PATH/promo-src-014.txt"
DST14="$ROOT/LOGS/promo-dst-014.txt"
rm -f "$DST14"
echo "promo-content-014" > "$SRC14"
HASH14="sha256:$(python3 -c "import hashlib; print(hashlib.sha256(open('$SRC14','rb').read()).hexdigest())")"

FIXTURE14="$TMPDIR_LOCAL/promo_exec_tamper.json"
cat > "$FIXTURE14" <<EOF
{
  "tool": "FS_PROMOTE",
  "args": {"src_path": "$SRC14", "dst_path": "$DST14"},
  "intent": {
    "goal": "Tamper test promotion.",
    "expected_outputs": [{"ref": "file:dst_path", "value": "$DST14"}],
    "promotion_id": "promo-exec-014",
    "src_root_id": "runtime",
    "dst_root_id": "canonical_repo",
    "src_content_hash_sha256": "$HASH14",
    "allowed_artifact_class": "vetted_output",
    "requested_by": "test-actor"
  }
}
EOF

j14="$(python3 "$EVAL" "$FIXTURE14")"
TAMPERED14="$TMPDIR_LOCAL/promo_tampered_014.json"
# Replace the record_hash with a bogus value.
python3 -c "
import json, sys
rec = json.loads(sys.stdin.read())
rec['record_hash'] = 'sha256:0000000000000000000000000000000000000000000000000000000000000000'
print(json.dumps(rec, indent=2))
" <<< "$j14" > "$TAMPERED14"

if python3 "$EXEC" "$TAMPERED14" >/dev/null 2>&1; then
  echo "FAIL: T-PROMO-014 exec should have rejected tampered record but exited 0"
  fail=$((fail+1))
else
  echo "PASS: T-PROMO-014 exec correctly rejected tampered record (exit non-zero)"
  pass=$((pass+1))
fi

# Destination must not have been created.
assert_contains "T-PROMO-014 dst not created after tamper" "$(test ! -f "$DST14" && echo absent)" "absent"

echo
# ---------------------------------------------------------------------------
# T-PROMO-015: destination hash mismatch fail-closed (INV-PROMO-004)
# Uses GOV_PROMO_TEST_DST_CORRUPTION=1 to inject a byte corruption into the
# destination after copy, triggering the RC-PROMO-HASH-MISMATCH-DST path.
# ---------------------------------------------------------------------------
echo "--- T-PROMO-015: dst hash mismatch fail-closed (INV-PROMO-004) ---"

SRC15="$GOV_RUNTIME_PATH/promo-src-015.txt"
DST15="$ROOT/LOGS/promo-dst-015.txt"
rm -f "$DST15"
echo "promo-content-015" > "$SRC15"
HASH15="sha256:$(python3 -c "import hashlib; print(hashlib.sha256(open('$SRC15','rb').read()).hexdigest())")"

FIXTURE15="$TMPDIR_LOCAL/promo_exec_dst_corrupt.json"
cat > "$FIXTURE15" <<EOF
{
  "tool": "FS_PROMOTE",
  "args": {"src_path": "$SRC15", "dst_path": "$DST15"},
  "intent": {
    "goal": "Dst corruption test promotion.",
    "expected_outputs": [{"ref": "file:dst_path", "value": "$DST15"}],
    "promotion_id": "promo-exec-015",
    "src_root_id": "runtime",
    "dst_root_id": "canonical_repo",
    "src_content_hash_sha256": "$HASH15",
    "allowed_artifact_class": "vetted_output",
    "requested_by": "test-actor"
  }
}
EOF

j15="$(python3 "$EVAL" "$FIXTURE15")"
echo "$j15" > "$ROOT/LOGS/t-promo-015-decision.record.json"

if echo "$j15" | grep -q '"policy_decision": "ALLOW"'; then
  exec_rc15=0
  exec_out15="$(GOV_PROMO_TEST_DST_CORRUPTION=1 python3 "$EXEC" "$ROOT/LOGS/t-promo-015-decision.record.json" 2>/dev/null)" || exec_rc15=$?
  echo "$exec_out15" > "$ROOT/LOGS/t-promo-015-completion.record.json"

  if [[ $exec_rc15 -ne 0 ]]; then
    echo "PASS: T-PROMO-015 exec exit non-zero on dst corruption (fail-closed)"
    pass=$((pass+1))
  else
    echo "FAIL: T-PROMO-015 exec should have failed on dst hash mismatch but exited 0"
    fail=$((fail+1))
  fi

  assert_contains "T-PROMO-015 outcome FAIL_DST_HASH_MISMATCH" "$exec_out15" '"completion_outcome": "FAIL_DST_HASH_MISMATCH"'
  assert_contains "T-PROMO-015 reason HASH-MISMATCH-DST"        "$exec_out15" 'RC-PROMO-HASH-MISMATCH-DST'
  assert_contains "T-PROMO-015 dst_hash_verified false"          "$exec_out15" '"dst_hash_verified": false'
  verify_hash     "T-PROMO-015 completion verify-record"        "$ROOT/LOGS/t-promo-015-completion.record.json"
else
  echo "FAIL: T-PROMO-015 setup: policy-eval did not return ALLOW"
  echo "$j15"
  fail=$((fail+1))
fi

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
