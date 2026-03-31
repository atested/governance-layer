#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task165-repo-packaging.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

run_check() {
  local out="$1"
  {
    echo "--- T-REPO-PACKAGING-001: required top-level external files present ---"
    local required=(
      "README.md"
      "docs/EXTERNAL_CONTRACTS.md"
      "docs/TEST-SUITE.md"
      "system/scripts/bootstrap-run.sh"
      "system/scripts/release-gate.sh"
    )
    for f in "${required[@]}"; do
      if [[ -f "$ROOT/$f" ]]; then
        echo "PASS: required file present: $f"
      else
        echo "FAIL: missing required file: $f"
        exit 1
      fi
    done

    echo "--- T-REPO-PACKAGING-002: forbidden local-only artifacts absent ---"
    python3 - <<'PY' "$ROOT"
import subprocess, sys
from pathlib import PurePosixPath

root = sys.argv[1]
proc = subprocess.run(
    ["git", "-C", root, "ls-files"],
    check=True,
    text=True,
    capture_output=True,
)
tracked = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
hits = []
for rel in tracked:
    p = PurePosixPath(rel)
    if rel.startswith("out/proof-bundles/"):
        hits.append(rel)
    if rel.startswith(".venv/"):
        hits.append(rel)
    if "__pycache__" in p.parts:
        hits.append(rel)
    if p.name == ".DS_Store":
        hits.append(rel)
    if p.name.endswith(".swp"):
        hits.append(rel)
    if rel.startswith(".pytest_cache/"):
        hits.append(rel)
if hits:
    for h in sorted(set(hits)):
        print(f"FAIL: forbidden tracked artifact present: {h}")
    raise SystemExit(1)
print("PASS: forbidden tracked artifacts absent")
PY
  } > "$out"
}

run_check "$TMPDIR_LOCAL/run1.out"
run_check "$TMPDIR_LOCAL/run2.out"
D1="$(sha256_file "$TMPDIR_LOCAL/run1.out")"
D2="$(sha256_file "$TMPDIR_LOCAL/run2.out")"
cat "$TMPDIR_LOCAL/run1.out"
echo "REPO_PACKAGING_SHA256_RUN1=$D1"
echo "REPO_PACKAGING_SHA256_RUN2=$D2"
[[ "$D1" == "$D2" ]] || { echo "FAIL: repo packaging output nondeterministic"; exit 1; }
echo "PASS: repo packaging check output deterministic across two runs"
