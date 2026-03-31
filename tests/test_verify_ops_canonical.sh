#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task119-ops-canonical.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

run_internal() {
  python3 "$ROOT/scripts/verify-ops-canonical.py" --selftest
  cat > "$TMPDIR_LOCAL/docblock_ok.sh" <<'SH'
#!/usr/bin/env bash
# FORBIDDEN_COMMANDS_LIST_BEGIN
# git merge main
# FORBIDDEN_COMMANDS_LIST_END
echo ok
SH
  python3 "$ROOT/scripts/verify-ops-canonical.py" --check-file "$TMPDIR_LOCAL/docblock_ok.sh"
  cat > "$TMPDIR_LOCAL/real_violation.sh" <<'SH'
#!/usr/bin/env bash
git switch main
SH
  python3 "$ROOT/scripts/verify-ops-canonical.py" --check-file "$TMPDIR_LOCAL/real_violation.sh"
}

if [[ "${1:-}" == "--internal-run" ]]; then
  run_internal
  exit 0
fi

echo "--- T-OPS-CANON-001: verifier selftest passes ---"
python3 "$ROOT/scripts/verify-ops-canonical.py" --selftest > "$TMPDIR_LOCAL/selftest.out"
grep -q '^OK$' "$TMPDIR_LOCAL/selftest.out"
echo "PASS: selftest reports OK"

echo
echo "--- T-OPS-CANON-002: docblock-forbidden markers ignored in --check-file ---"
cat > "$TMPDIR_LOCAL/docblock_ok.sh" <<'SH'
#!/usr/bin/env bash
# FORBIDDEN_COMMANDS_LIST_BEGIN
# git merge main
# git switch main
# FORBIDDEN_COMMANDS_LIST_END
echo ok
SH
DOCBLOCK_OUT="$(python3 "$ROOT/scripts/verify-ops-canonical.py" --check-file "$TMPDIR_LOCAL/docblock_ok.sh")"
echo "$DOCBLOCK_OUT"
[[ "$DOCBLOCK_OUT" == "OK" ]] || { echo "FAIL: docblock ignore case should be OK"; exit 1; }
echo "PASS: docblock ignore case"

echo
echo "--- T-OPS-CANON-003: real forbidden command is detected ---"
cat > "$TMPDIR_LOCAL/real_violation.sh" <<'SH'
#!/usr/bin/env bash
git switch main
SH
NEG_OUT="$(python3 "$ROOT/scripts/verify-ops-canonical.py" --check-file "$TMPDIR_LOCAL/real_violation.sh")"
echo "$NEG_OUT"
[[ "$NEG_OUT" == "FORBIDDEN" ]] || { echo "FAIL: negative control should be FORBIDDEN"; exit 1; }
echo "PASS: negative control detects forbidden behavior"

echo
bash "$0" --internal-run > "$TMPDIR_LOCAL/run1.out"
bash "$0" --internal-run > "$TMPDIR_LOCAL/run2.out"
H1="$(sha256_file "$TMPDIR_LOCAL/run1.out")"
H2="$(sha256_file "$TMPDIR_LOCAL/run2.out")"
echo "VERIFY_OPS_CANONICAL_SHA256_RUN1=$H1"
echo "VERIFY_OPS_CANONICAL_SHA256_RUN2=$H2"
[[ "$H1" == "$H2" ]] || { echo "FAIL: verify-ops-canonical test output nondeterministic"; exit 1; }
echo "PASS: verify-ops-canonical test output deterministic across two runs"
