#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# Legacy allowlist for existing scripts not yet migrated.
ALLOW_RE='^(scripts/dev/precommit-guard-assignments\.sh|system/tests/generate_aat_golden_fixtures\.sh|system/tests/test_aat_determinism\.sh|system/tests/test_aat_integration\.sh|system/tests/test_aat_kernel\.sh|system/tests/test_audit_artifact_helper\.sh|system/tests/test_determinism_harness\.sh|system/tests/test_evidence_bundle_lint\.sh|system/tests/test_evidence_path_standardizer\.sh|system/tests/test_foundation_v0_process_ledger\.sh|system/tests/test_hot_file_scan\.sh|system/tests/test_local_ci_minimal\.sh|system/tests/test_no_spec_no_task_preflight\.sh|system/tests/test_proof_bundle_verifier_ux\.sh|system/tests/test_release_gate_summary_parser\.sh|system/tests/test_repo_tripwire\.sh|system/tests/test_stop_packet_generator\.sh|system/tests/test_wrong_execution_root_doc\.sh)$'

while IFS= read -r f; do
  [[ -x "$f" ]] || continue
  head1="$(sed -n '1p' "$f")"
  if [[ "$head1" != '#!/usr/bin/env bash' ]]; then
    if [[ ! "$f" =~ $ALLOW_RE ]]; then
      echo "$f:1"
    fi
    continue
  fi
  head2="$(sed -n '2p' "$f")"
  if [[ "$head2" != 'set -euo pipefail' ]]; then
    if [[ ! "$f" =~ $ALLOW_RE ]]; then
      echo "$f:2"
    fi
  fi
done < <(git ls-files 'scripts/*.sh' 'system/tests/*.sh' | sort) > "$tmp"

if [[ -s "$tmp" ]]; then
  sort -u "$tmp"
  echo "FAIL:STRICT_MODE_HEADER_MISSING"
  exit 1
fi

echo "CASE=SHELL_STRICT_MODE PASS"
