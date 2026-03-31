#!/usr/bin/env bash
# Test AAT integration (aat_main.py orchestrator with all validators)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FIXTURES_DIR="$SCRIPT_DIR/fixtures/aat/integration"

# Test counters
PASS=0
FAIL=0

# Test result tracking
TEST_RESULTS=()

# Color output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_pass() {
  echo -e "${GREEN}[PASS]${NC} $1"
  PASS=$((PASS + 1))
  TEST_RESULTS+=("PASS: $1")
}

log_fail() {
  echo -e "${RED}[FAIL]${NC} $1"
  FAIL=$((FAIL + 1))
  TEST_RESULTS+=("FAIL: $1")
}

log_info() {
  echo -e "${YELLOW}[INFO]${NC} $1"
}

# Create test fixture directory
mkdir -p "$FIXTURES_DIR"

# Helper: Create minimal valid action bundle
create_valid_bundle() {
  local bundle_dir="$1"
  mkdir -p "$bundle_dir"

  # Input Manifest
  cat > "$bundle_dir/input_manifest.json" <<'EOF'
{
  "input_manifest_version": "v0",
  "inputs": []
}
EOF

  # Constraint Set Digest (empty)
  cat > "$bundle_dir/constraint_set_digest.json" <<'EOF'
{
  "csd_version": "v0",
  "constraints": []
}
EOF

  # Constraint Acknowledgment Map (empty)
  cat > "$bundle_dir/constraint_acknowledgment_map.json" <<'EOF'
{
  "cam_version": "v0",
  "acknowledgments": []
}
EOF

  # Method Binding
  cat > "$bundle_dir/method_binding.json" <<'EOF'
{
  "method_binding_version": "v0",
  "method_id": "generic_exec",
  "action_kind": "CORE_GENERIC"
}
EOF

  # Assumptions and Unknowns Register (empty)
  cat > "$bundle_dir/assumptions_unknowns_register.json" <<'EOF'
{
  "aur_version": "v0",
  "assumptions": [],
  "unknowns": []
}
EOF

  # Claims-to-Evidence Map (empty)
  cat > "$bundle_dir/claims_evidence_map.json" <<'EOF'
{
  "cem_version": "v0",
  "claims": []
}
EOF
}

# Test integration: PASS case
test_integration_pass() {
  log_info "Testing integration: PASS case"

  local bundle_dir="$FIXTURES_DIR/pass"
  create_valid_bundle "$bundle_dir"

  # Run aat_main.py
  output=$(python3 "$REPO_ROOT/scripts/aat_main.py" \
    --bundle-dir "$bundle_dir" \
    --schema-dir "$REPO_ROOT/system/schemas" \
    --repo-root "$REPO_ROOT" 2>&1 || true)

  # Check for PASS decision
  if echo "$output" | grep -q "DECISION=PASS"; then
    log_pass "Integration: Valid bundle passed AAT"
  else
    log_fail "Integration: Valid bundle failed AAT"
    echo "  Output: $output"
  fi

  # Verify ADR structure
  adr_json=$(python3 "$REPO_ROOT/scripts/aat_main.py" \
    --bundle-dir "$bundle_dir" \
    --schema-dir "$REPO_ROOT/system/schemas" \
    --repo-root "$REPO_ROOT" 2>/dev/null || true)

  if echo "$adr_json" | python3 -c "import sys,json; adr=json.load(sys.stdin); assert adr['decision']=='PASS'" 2>/dev/null; then
    log_pass "Integration: ADR has correct structure"
  else
    log_fail "Integration: ADR structure invalid"
  fi

  rm -rf "$bundle_dir"
}

# Test integration: K1 HARD_STOP case
test_integration_k1_hard_stop() {
  log_info "Testing integration: K1 HARD_STOP case"

  local bundle_dir="$FIXTURES_DIR/k1_hard_stop"
  create_valid_bundle "$bundle_dir"

  # Add phantom action
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

  # Run aat_main.py
  output=$(python3 "$REPO_ROOT/scripts/aat_main.py" \
    --bundle-dir "$bundle_dir" \
    --schema-dir "$REPO_ROOT/system/schemas" \
    --repo-root "$REPO_ROOT" 2>&1 || true)

  # Check for HARD_STOP decision
  if echo "$output" | grep -q "DECISION=FAIL_HARD_STOP"; then
    log_pass "Integration: K1 violation triggered HARD_STOP"
  else
    log_fail "Integration: K1 violation did not trigger HARD_STOP"
    echo "  Output: $output"
  fi

  # Check exit code (should be 2 for HARD_STOP)
  set +e
  python3 "$REPO_ROOT/scripts/aat_main.py" \
    --bundle-dir "$bundle_dir" \
    --schema-dir "$REPO_ROOT/system/schemas" \
    --repo-root "$REPO_ROOT" >/dev/null 2>&1
  exit_code=$?
  set -e

  if [ $exit_code -eq 2 ]; then
    log_pass "Integration: Exit code 2 for HARD_STOP"
  else
    log_fail "Integration: Exit code $exit_code (expected 2)"
  fi

  rm -rf "$bundle_dir"
}

# Test integration: Determinism (two-run SHA256 comparison)
test_integration_determinism() {
  log_info "Testing integration: Determinism"

  local bundle_dir="$FIXTURES_DIR/determinism"
  create_valid_bundle "$bundle_dir"

  # Run aat_main.py twice
  adr1=$(python3 "$REPO_ROOT/scripts/aat_main.py" \
    --bundle-dir "$bundle_dir" \
    --schema-dir "$REPO_ROOT/system/schemas" \
    --repo-root "$REPO_ROOT" 2>/dev/null || true)

  sleep 0.1  # Small delay to ensure different timestamps if any

  adr2=$(python3 "$REPO_ROOT/scripts/aat_main.py" \
    --bundle-dir "$bundle_dir" \
    --schema-dir "$REPO_ROOT/system/schemas" \
    --repo-root "$REPO_ROOT" 2>/dev/null || true)

  # Compute SHA256 hashes
  hash1=$(echo "$adr1" | shasum -a 256 | awk '{print $1}')
  hash2=$(echo "$adr2" | shasum -a 256 | awk '{print $1}')

  if [ "$hash1" == "$hash2" ]; then
    log_pass "Integration: Determinism validated (two runs produce identical ADR)"
  else
    log_fail "Integration: Non-deterministic output detected"
    echo "  Run 1 hash: $hash1"
    echo "  Run 2 hash: $hash2"
  fi

  rm -rf "$bundle_dir"
}

# Main test execution
main() {
  log_info "Starting AAT Integration Tests"
  log_info "Fixtures directory: $FIXTURES_DIR"

  test_integration_pass
  test_integration_k1_hard_stop
  test_integration_determinism

  echo ""
  echo "================================"
  echo "Test Summary"
  echo "================================"
  echo "PASS: $PASS"
  echo "FAIL: $FAIL"
  echo "TOTAL: $((PASS + FAIL))"
  echo ""

  if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
  else
    echo -e "${RED}Some tests failed${NC}"
    exit 1
  fi
}

main "$@"
