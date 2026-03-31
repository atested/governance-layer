#!/usr/bin/env bash
# Test: Codex ops process doc auto-loading
# Verifies:
# 1. Ops process doc is loaded and prepended to execution contract
# 2. Missing ops doc fails closed

set -euo pipefail

TEST_PASS_COUNT=0
TEST_FAIL_COUNT=0

test_pass() {
  local label="$1"
  echo "PASS: $label"
  TEST_PASS_COUNT=$((TEST_PASS_COUNT + 1))
}

test_fail() {
  local label="$1"
  echo "FAIL: $label"
  TEST_FAIL_COUNT=$((TEST_FAIL_COUNT + 1))
}

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

OPS_DOC="docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md"
UNATTENDED_SCRIPT="system/scripts/codex-unattended.sh"

echo "=== Test 1: Ops process doc exists and is referenced in codex-unattended.sh ==="
if [ ! -f "$OPS_DOC" ]; then
  test_fail "Ops process doc should exist at $OPS_DOC"
else
  test_pass "Ops process doc exists at $OPS_DOC"
fi

if grep -q "OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md" "$UNATTENDED_SCRIPT"; then
  test_pass "codex-unattended.sh references ops process doc"
else
  test_fail "codex-unattended.sh should reference ops process doc"
fi

echo ""
echo "=== Test 2: Verify ops doc loading logic in codex-unattended.sh ==="
# Check for fail-closed guards
if grep -q 'if \[\[ ! -f "\$ops_process_doc" \]\]; then' "$UNATTENDED_SCRIPT"; then
  test_pass "Has fail-closed guard for missing ops doc file"
else
  test_fail "Missing fail-closed guard for missing ops doc file"
fi

if grep -q 'if \[\[ ! -r "\$ops_process_doc" \]\]; then' "$UNATTENDED_SCRIPT"; then
  test_pass "Has fail-closed guard for unreadable ops doc"
else
  test_fail "Missing fail-closed guard for unreadable ops doc"
fi

# Check for ops doc prepending in execution contract
if grep -q 'cat "\$ops_process_doc"' "$UNATTENDED_SCRIPT"; then
  test_pass "Ops doc is prepended to execution contract"
else
  test_fail "Ops doc should be prepended to execution contract"
fi

echo ""
echo "=== Test 3: Verify ops doc content snippet ==="
# Check that ops doc contains expected content
if grep -q "ChatGPT + Codex + Cecil + Greg" "$OPS_DOC"; then
  test_pass "Ops doc contains expected title"
else
  test_fail "Ops doc should contain 'ChatGPT + Codex + Cecil + Greg'"
fi

if grep -q "Codex is the primary builder" "$OPS_DOC"; then
  test_pass "Ops doc contains Codex role definition"
else
  test_fail "Ops doc should contain Codex role definition"
fi

echo ""
echo "=== Test 4: Simulate missing ops doc scenario ==="
# Create a temporary test environment
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

# Copy unattended script to temp location and simulate execution
cp "$UNATTENDED_SCRIPT" "$TMP_DIR/codex-unattended.sh"

# Test that the script would fail if ops doc is missing
# We'll just verify the error message generation logic exists
if grep -A2 'if \[\[ ! -f "\$ops_process_doc" \]\]; then' "$UNATTENDED_SCRIPT" | grep -q 'err "Missing required ops process doc'; then
  test_pass "Missing ops doc triggers fail-closed error"
else
  test_fail "Missing ops doc should trigger fail-closed error"
fi

echo ""
echo "=== Summary ==="
echo "Pass: $TEST_PASS_COUNT"
echo "Fail: $TEST_FAIL_COUNT"

if [ "$TEST_FAIL_COUNT" -eq 0 ]; then
  echo "All tests passed"
  exit 0
else
  echo "Some tests failed"
  exit 1
fi
