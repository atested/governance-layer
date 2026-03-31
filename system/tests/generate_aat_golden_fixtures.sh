#!/usr/bin/env bash
# Generate AAT golden fixtures for all reason codes + PASS cases

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GOLDEN_PASS="$SCRIPT_DIR/fixtures/aat/golden_pass"
GOLDEN_FAIL="$SCRIPT_DIR/fixtures/aat/golden_fail"

mkdir -p "$GOLDEN_PASS" "$GOLDEN_FAIL"

echo "Generating AAT golden fixtures..."

# Helper: Create base valid bundle
create_base_bundle() {
  local bundle_dir="$1"
  mkdir -p "$bundle_dir"

  cat > "$bundle_dir/input_manifest.json" <<'EOF'
{
  "input_manifest_version": "v0",
  "inputs": []
}
EOF

  cat > "$bundle_dir/constraint_set_digest.json" <<'EOF'
{
  "csd_version": "v0",
  "constraints": []
}
EOF

  cat > "$bundle_dir/constraint_acknowledgment_map.json" <<'EOF'
{
  "cam_version": "v0",
  "acknowledgments": []
}
EOF

  cat > "$bundle_dir/method_binding.json" <<'EOF'
{
  "method_binding_version": "v0",
  "method_id": "generic_exec",
  "action_kind": "CORE_GENERIC"
}
EOF

  cat > "$bundle_dir/assumptions_unknowns_register.json" <<'EOF'
{
  "aur_version": "v0",
  "assumptions": [],
  "unknowns": []
}
EOF

  cat > "$bundle_dir/claims_evidence_map.json" <<'EOF'
{
  "cem_version": "v0",
  "claims": []
}
EOF
}

# PASS case: CORE_GENERIC profile
echo "  Creating PASS_CORE_GENERIC..."
bundle_dir="$GOLDEN_PASS/core_generic"
create_base_bundle "$bundle_dir"
python3 "$REPO_ROOT/scripts/aat_main.py" \
  --bundle-dir "$bundle_dir" \
  --schema-dir "$REPO_ROOT/system/schemas" \
  --output "$bundle_dir/expected_adr.json" \
  2>/dev/null

# PASS case: TOOL_EXEC profile
echo "  Creating PASS_TOOL_EXEC..."
bundle_dir="$GOLDEN_PASS/tool_exec"
create_base_bundle "$bundle_dir"
cat > "$bundle_dir/method_binding.json" <<'EOF'
{
  "method_binding_version": "v0",
  "method_id": "tool_exec",
  "action_kind": "TOOL_EXEC"
}
EOF
python3 "$REPO_ROOT/scripts/aat_main.py" \
  --bundle-dir "$bundle_dir" \
  --schema-dir "$REPO_ROOT/system/schemas" \
  --output "$bundle_dir/expected_adr.json" \
  2>/dev/null

# FAIL case: K1 - Phantom action
echo "  Creating FAIL_K1_PHANTOM_ACTION..."
bundle_dir="$GOLDEN_FAIL/k1_phantom_action"
create_base_bundle "$bundle_dir"
cat > "$bundle_dir/claims_evidence_map.json" <<'EOF'
{
  "cem_version": "v0",
  "claims": [
    {
      "claim_id": "cl-001",
      "claim_type": "verification_completed",
      "evidence_refs": []
    }
  ]
}
EOF
python3 "$REPO_ROOT/scripts/aat_main.py" \
  --bundle-dir "$bundle_dir" \
  --schema-dir "$REPO_ROOT/system/schemas" \
  --output "$bundle_dir/expected_adr.json" \
  2>/dev/null || true

# FAIL case: K2 - Undeclared dependency
echo "  Creating FAIL_K2_UNDECLARED_DEPENDENCY..."
bundle_dir="$GOLDEN_FAIL/k2_undeclared_dependency"
create_base_bundle "$bundle_dir"
cat > "$bundle_dir/claims_evidence_map.json" <<'EOF'
{
  "cem_version": "v0",
  "claims": [
    {
      "claim_id": "cl-001",
      "claim_type": "analysis_completed",
      "evidence_refs": [
        {
          "ref_type": "file_digest",
          "digest": "sha256:9999999999999999999999999999999999999999999999999999999999999999"
        }
      ]
    }
  ]
}
EOF
python3 "$REPO_ROOT/scripts/aat_main.py" \
  --bundle-dir "$bundle_dir" \
  --schema-dir "$REPO_ROOT/system/schemas" \
  --output "$bundle_dir/expected_adr.json" \
  2>/dev/null || true

# FAIL case: K3 - Constraint unacknowledged
echo "  Creating FAIL_K3_CONSTRAINT_UNACKNOWLEDGED..."
bundle_dir="$GOLDEN_FAIL/k3_constraint_unacknowledged"
create_base_bundle "$bundle_dir"
cat > "$bundle_dir/constraint_set_digest.json" <<'EOF'
{
  "csd_version": "v0",
  "constraints": [
    {
      "constraint_id": "c-001",
      "constraint_version": "v1",
      "constraint_type": "no_network"
    }
  ]
}
EOF
python3 "$REPO_ROOT/scripts/aat_main.py" \
  --bundle-dir "$bundle_dir" \
  --schema-dir "$REPO_ROOT/system/schemas" \
  --output "$bundle_dir/expected_adr.json" \
  2>/dev/null || true

# FAIL case: K4 - Method missing or forbidden
echo "  Creating FAIL_K4_METHOD_MISSING_OR_FORBIDDEN..."
bundle_dir="$GOLDEN_FAIL/k4_method_forbidden"
create_base_bundle "$bundle_dir"
cat > "$bundle_dir/method_binding.json" <<'EOF'
{
  "method_binding_version": "v0",
  "method_id": "invalid_method",
  "action_kind": "CORE_GENERIC"
}
EOF
python3 "$REPO_ROOT/scripts/aat_main.py" \
  --bundle-dir "$bundle_dir" \
  --schema-dir "$REPO_ROOT/system/schemas" \
  --output "$bundle_dir/expected_adr.json" \
  2>/dev/null || true

# FAIL case: K5 - Version binding missing (tested via ADR validation - skip for now)
echo "  Skipping K5 (requires ADR validation)"

# FAIL case: M1 - Schema invalid
echo "  Creating FAIL_M1_SCHEMA_INVALID..."
bundle_dir="$GOLDEN_FAIL/m1_schema_invalid"
create_base_bundle "$bundle_dir"
cat > "$bundle_dir/input_manifest.json" <<'EOF'
{
  "input_manifest_version": "v0",
  "inputs": [],
  "unknown_field": "invalid"
}
EOF
python3 "$REPO_ROOT/scripts/aat_main.py" \
  --bundle-dir "$bundle_dir" \
  --schema-dir "$REPO_ROOT/system/schemas" \
  --output "$bundle_dir/expected_adr.json" \
  2>/dev/null || true

# FAIL case: P1 - Canonical idempotence fail (hard to create genuine case - skip)
echo "  Skipping P1 (canonical idempotence guaranteed by json.dumps)"

# FAIL case: P2 - Round-trip fail (hard to create genuine case - skip)
echo "  Skipping P2 (round-trip guaranteed by JSON spec)"

# FAIL case: C1 - Contradiction detected
echo "  Creating FAIL_C1_CONTRADICTION_DETECTED..."
bundle_dir="$GOLDEN_FAIL/c1_contradiction"
create_base_bundle "$bundle_dir"
cat > "$bundle_dir/constraint_set_digest.json" <<'EOF'
{
  "csd_version": "v0",
  "constraints": [
    {
      "constraint_id": "c-001",
      "constraint_version": "v1",
      "constraint_type": "no_network"
    }
  ]
}
EOF
cat > "$bundle_dir/constraint_acknowledgment_map.json" <<'EOF'
{
  "cam_version": "v0",
  "acknowledgments": [
    {
      "constraint_id": "c-001",
      "status": "satisfied"
    },
    {
      "constraint_id": "c-001",
      "status": "unknown"
    }
  ]
}
EOF
python3 "$REPO_ROOT/scripts/aat_main.py" \
  --bundle-dir "$bundle_dir" \
  --schema-dir "$REPO_ROOT/system/schemas" \
  --output "$bundle_dir/expected_adr.json" \
  2>/dev/null || true

# FAIL case: C2 - Evidence ref not in IM
echo "  Creating FAIL_C2_EVIDENCE_REF_NOT_IN_IM..."
bundle_dir="$GOLDEN_FAIL/c2_evidence_not_in_im"
create_base_bundle "$bundle_dir"
cat > "$bundle_dir/claims_evidence_map.json" <<'EOF'
{
  "cem_version": "v0",
  "claims": [
    {
      "claim_id": "cl-001",
      "claim_type": "analysis_completed",
      "evidence_refs": [
        {
          "ref_type": "file_digest",
          "digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        }
      ]
    }
  ]
}
EOF
python3 "$REPO_ROOT/scripts/aat_main.py" \
  --bundle-dir "$bundle_dir" \
  --schema-dir "$REPO_ROOT/system/schemas" \
  --output "$bundle_dir/expected_adr.json" \
  2>/dev/null || true

# FAIL case: C3 - Forbidden claim without evidence
echo "  Creating FAIL_C3_FORBIDDEN_CLAIM_NO_EVIDENCE..."
bundle_dir="$GOLDEN_FAIL/c3_forbidden_claim"
create_base_bundle "$bundle_dir"
cat > "$bundle_dir/claims_evidence_map.json" <<'EOF'
{
  "cem_version": "v0",
  "claims": [
    {
      "claim_id": "cl-001",
      "claim_type": "test_passed",
      "evidence_refs": []
    }
  ]
}
EOF
python3 "$REPO_ROOT/scripts/aat_main.py" \
  --bundle-dir "$bundle_dir" \
  --schema-dir "$REPO_ROOT/system/schemas" \
  --output "$bundle_dir/expected_adr.json" \
  2>/dev/null || true

echo ""
echo "Golden fixtures generated:"
echo "  PASS cases: $(ls -1 "$GOLDEN_PASS" | wc -l)"
echo "  FAIL cases: $(ls -1 "$GOLDEN_FAIL" | wc -l)"
echo ""
echo "Fixtures location:"
echo "  $GOLDEN_PASS"
echo "  $GOLDEN_FAIL"
