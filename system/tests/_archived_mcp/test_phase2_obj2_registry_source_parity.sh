#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

python3 - "$ROOT" <<'PY'
import hashlib
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
policy = (root / "scripts/policy-eval.py").read_text(encoding="utf-8")
mcp = (root / "mcp/server.py").read_text(encoding="utf-8")
registry = root / "capabilities/capability-registry.json"

if not registry.is_file():
    print("FAIL: registry missing")
    sys.exit(1)

# Ensure both sources pin the same canonical registry relative path.
if '"capabilities" / "capability-registry.json"' not in policy:
    print("FAIL: policy registry path contract missing")
    sys.exit(1)
if '"capabilities" / "capability-registry.json"' not in mcp:
    print("FAIL: mcp registry path contract missing")
    sys.exit(1)

# Ensure policy-eval loads internally and not from caller argv as source-of-truth.
if "load_internal_registry" not in policy:
    print("FAIL: load_internal_registry missing")
    sys.exit(1)
if "argv[1] is ignored" not in policy:
    print("FAIL: internal registry source guard missing")
    sys.exit(1)

# Deterministic digest check used by both policy/verify contract.
raw = registry.read_bytes()
digest = "sha256:" + hashlib.sha256(raw).hexdigest()

# verify-record.py computes cap hash from same registry bytes.
verify = (root / "scripts/verify-record.py").read_text(encoding="utf-8")
if "compute_cap_registry_hash" not in verify:
    print("FAIL: verify cap hash function missing")
    sys.exit(1)

print(f"OBJ2_REGISTRY_DIGEST={digest}")
print("CASE=OBJ2_REGISTRY_SOURCE_PARITY PASS")
PY
