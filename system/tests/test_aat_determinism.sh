#!/usr/bin/env bash
# Test AAT determinism - verify two-run SHA256 comparison

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GOLDEN_PASS="$SCRIPT_DIR/fixtures/aat/golden_pass"
GOLDEN_FAIL="$SCRIPT_DIR/fixtures/aat/golden_fail"

# Test counters
PASS=0
FAIL=0

# Color output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_pass() {
  echo -e "${GREEN}[PASS]${NC} $1"
  PASS=$((PASS + 1))
}

log_fail() {
  echo -e "${RED}[FAIL]${NC} $1"
  FAIL=$((FAIL + 1))
}

log_info() {
  echo -e "${YELLOW}[INFO]${NC} $1"
}

# Test determinism for a single bundle
test_bundle_determinism() {
  local bundle_name="$1"
  local bundle_dir="$2"

  # Run AAT twice with small delay
  adr1=$(python3 "$REPO_ROOT/scripts/aat_main.py" \
    --bundle-dir "$bundle_dir" \
    --schema-dir "$REPO_ROOT/system/schemas" \
    2>/dev/null || true)

  sleep 0.05  # Small delay to ensure different timestamps if any

  adr2=$(python3 "$REPO_ROOT/scripts/aat_main.py" \
    --bundle-dir "$bundle_dir" \
    --schema-dir "$REPO_ROOT/system/schemas" \
    2>/dev/null || true)

  # Compute SHA256 hashes
  hash1=$(echo "$adr1" | shasum -a 256 | awk '{print $1}')
  hash2=$(echo "$adr2" | shasum -a 256 | awk '{print $1}')

  # Compare hashes
  if [ "$hash1" == "$hash2" ]; then
    log_pass "Determinism: $bundle_name (SHA256 match)"
  else
    log_fail "Determinism: $bundle_name (SHA256 mismatch)"
    echo "  Run 1: $hash1"
    echo "  Run 2: $hash2"
    echo "  ADR 1: $adr1" | head -3
    echo "  ADR 2: $adr2" | head -3
  fi
}

# Main test execution
main() {
  log_info "Starting AAT Determinism Tests"
  log_info "Testing two-run SHA256 comparison for all golden fixtures"
  echo ""

  # Test PASS cases
  log_info "Testing PASS cases..."
  for bundle_dir in "$GOLDEN_PASS"/*; do
    if [ -d "$bundle_dir" ]; then
      bundle_name=$(basename "$bundle_dir")
      test_bundle_determinism "PASS/$bundle_name" "$bundle_dir"
    fi
  done

  # Test FAIL cases
  log_info "Testing FAIL cases..."
  for bundle_dir in "$GOLDEN_FAIL"/*; do
    if [ -d "$bundle_dir" ]; then
      bundle_name=$(basename "$bundle_dir")
      test_bundle_determinism "FAIL/$bundle_name" "$bundle_dir"
    fi
  done

  echo ""
  echo "================================"
  echo "Determinism Test Summary"
  echo "================================"
  echo "PASS: $PASS"
  echo "FAIL: $FAIL"
  echo "TOTAL: $((PASS + FAIL))"
  echo ""

  if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}All determinism tests passed!${NC}"
    echo "AAT produces identical outputs for identical inputs (no wall clock, network, or LLM dependencies)"
    exit 0
  else
    echo -e "${RED}Determinism failures detected${NC}"
    exit 1
  fi
}

main "$@"
