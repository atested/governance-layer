#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

START_REF="$(git rev-parse --abbrev-ref HEAD)"
restore_ref() {
  git checkout -q "$START_REF" >/dev/null 2>&1 || true
}
trap restore_ref EXIT

echo "--- T-BASELINE-GATE-001: baseline gate exists and is executable ---"
test -f system/scripts/baseline-gate.sh
chmod +x system/scripts/baseline-gate.sh
echo "PASS: baseline-gate present"

echo "--- T-BASELINE-GATE-002: clean baseline passes ---"
out1="$(system/scripts/baseline-gate.sh --repo "." --allow-out "out/" 2>&1)"
echo "$out1" | rg -q "BASELINE_OK"
echo "PASS: clean baseline"

# baseline-gate checks out main; return to starting ref for deterministic fixture setup
restore_ref

echo "--- T-BASELINE-GATE-003: untracked junk (non-out) is auto-cleaned ---"
junk_dir="tests/.baseline_gate_junk_dir"
junk_file="tests/.baseline_gate_junk_file"
rm -rf "$junk_dir" "$junk_file" || true
mkdir -p "$junk_dir"
echo "junk" > "$junk_file"

system/scripts/baseline-gate.sh --repo "." --allow-out "out/" >/tmp/baseline_gate_out.txt 2>/tmp/baseline_gate_err.txt

# baseline-gate checks out main; return to starting ref before assertions
restore_ref

test ! -e "$junk_dir"
test ! -e "$junk_file"
echo "PASS: untracked junk cleaned"

echo "--- T-BASELINE-GATE-004: tracked modification triggers STOP (exit 3) ---"
target="README.md"
test -f "$target"
printf "\n" >> "$target"

set +e
system/scripts/baseline-gate.sh --repo "." --allow-out "out/" >/tmp/baseline_gate_out2.txt 2>/tmp/baseline_gate_err2.txt
rc=$?
set -e

# baseline-gate checks out main; return and clean local tracked change
restore_ref
git checkout -q -- "$target"
test "$rc" -eq 3
echo "PASS: tracked modification STOP (exit=3)"

echo "Summary: baseline gate tests complete"
