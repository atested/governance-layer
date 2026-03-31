#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task137-release-gate-profiles.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

BAD_FIX="$TMPDIR_LOCAL/missing-fixture"

echo "--- T-RELEASE-GATE-PROFILE-001: dev profile is informational and non-gating ---"
GOV_PROFILE=dev RELEASE_GATE_SKIP_BASE=1 RELEASE_GATE_PROOF_PACKET_FIXTURE_ROOT="$BAD_FIX" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/dev1.out"
GOV_PROFILE=dev RELEASE_GATE_SKIP_BASE=1 RELEASE_GATE_PROOF_PACKET_FIXTURE_ROOT="$BAD_FIX" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/dev2.out"
grep -q 'INFO: proof-packet strictness source=profile GOV_PROFILE=dev value=0' "$TMPDIR_LOCAL/dev1.out"
grep -q 'INFO: proof-packet check skipped reason=missing_fixture' "$TMPDIR_LOCAL/dev1.out"
D1="$(sha256_file "$TMPDIR_LOCAL/dev1.out")"
D2="$(sha256_file "$TMPDIR_LOCAL/dev2.out")"
[[ "$D1" == "$D2" ]] || { echo "FAIL: dev profile output nondeterministic"; exit 1; }
echo "DEV_PROFILE_SHA256_RUN1=$D1"
echo "DEV_PROFILE_SHA256_RUN2=$D2"
echo "PASS: dev profile informational behavior deterministic"

echo
echo "--- T-RELEASE-GATE-PROFILE-002: ci profile is gating and fails closed when unavailable ---"
set +e
GOV_PROFILE=ci RELEASE_GATE_SKIP_BASE=1 RELEASE_GATE_PROOF_PACKET_FIXTURE_ROOT="$BAD_FIX" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/ci.out" 2>&1
rc=$?
set -e
[[ "$rc" == "1" ]] || { echo "FAIL: ci profile expected rc=1 got $rc"; exit 1; }
grep -q 'INFO: proof-packet strictness source=profile GOV_PROFILE=ci value=1' "$TMPDIR_LOCAL/ci.out"
grep -q 'FAIL: proof-packet check required but unavailable reason=missing_fixture' "$TMPDIR_LOCAL/ci.out"
echo "PASS: ci profile fails closed deterministically when proof-packet check unavailable (rc=$rc)"

echo
echo "--- T-RELEASE-GATE-PROFILE-003: explicit env override wins over profile ---"
GOV_PROFILE=ci RELEASE_GATE_STRICT_PROOF_PACKET=0 RELEASE_GATE_SKIP_BASE=1 RELEASE_GATE_PROOF_PACKET_FIXTURE_ROOT="$BAD_FIX" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/override.out"
grep -q 'INFO: proof-packet strictness source=env_override value=0' "$TMPDIR_LOCAL/override.out"
grep -q 'INFO: proof-packet check skipped reason=missing_fixture' "$TMPDIR_LOCAL/override.out"
echo "PASS: explicit RELEASE_GATE_STRICT_PROOF_PACKET overrides GOV_PROFILE"

