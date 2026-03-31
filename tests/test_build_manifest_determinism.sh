#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
FIXTURE="$ROOT/tests/fixtures/canon_001a.json"
LOG_DIR="$ROOT/LOGS"

pass=0
fail=0

assert_eq () {
  local name="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS: $name"
    pass=$((pass+1))
  else
    echo "FAIL: $name"
    echo "  got : $got"
    echo "  want: $want"
    fail=$((fail+1))
  fi
}

json_sha256 () {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())
PY
}

mkdir -p "$LOG_DIR"
RUN1_DIR="$(mktemp -d "$LOG_DIR/t-manifestdet-001-run1.XXXXXX")"
RUN2_DIR="$(mktemp -d "$LOG_DIR/t-manifestdet-001-run2.XXXXXX")"
MANIFEST1="$RUN1_DIR/MANIFEST.json"
MANIFEST2="$RUN2_DIR/MANIFEST.json"

echo "--- T-MANIFESTDET-001: MANIFEST.json stable across repeated runs ---"
GOV_BUILD_MANIFEST_PATH="$MANIFEST1" python3 "$EVAL" "$FIXTURE" > "$RUN1_DIR/record.json"
GOV_BUILD_MANIFEST_PATH="$MANIFEST2" python3 "$EVAL" "$FIXTURE" > "$RUN2_DIR/record.json"

if [[ -f "$MANIFEST1" ]]; then
  echo "PASS: T-MANIFESTDET-001 run1 manifest exists"
  pass=$((pass+1))
else
  echo "FAIL: T-MANIFESTDET-001 run1 manifest missing"
  fail=$((fail+1))
fi

if [[ -f "$MANIFEST2" ]]; then
  echo "PASS: T-MANIFESTDET-001 run2 manifest exists"
  pass=$((pass+1))
else
  echo "FAIL: T-MANIFESTDET-001 run2 manifest missing"
  fail=$((fail+1))
fi

if cmp -s "$MANIFEST1" "$MANIFEST2"; then
  echo "PASS: T-MANIFESTDET-001 manifests are byte-identical"
  pass=$((pass+1))
else
  echo "FAIL: T-MANIFESTDET-001 manifests differ"
  diff -u "$MANIFEST1" "$MANIFEST2" || true
  fail=$((fail+1))
fi

hash1="$(json_sha256 "$MANIFEST1")"
hash2="$(json_sha256 "$MANIFEST2")"
assert_eq "T-MANIFESTDET-001 manifest sha256 identical across runs" "$hash1" "$hash2"
echo "MANIFEST_SHA256_RUN1=$hash1"
echo "MANIFEST_SHA256_RUN2=$hash2"

echo
echo "--- T-MANIFESTDET-002: manifest excludes volatile/path-bearing fields ---"
rc_002=0
python3 - <<'PY' "$MANIFEST1" || rc_002=$?
import json, sys
from pathlib import Path

p = Path(sys.argv[1])
raw = p.read_text(encoding="utf-8")
m = json.loads(raw)

required = [
    "cap_registry_hash",
    "capability_class",
    "manifest_version",
    "normalized_args_hash",
    "policy_decision",
    "reason_codes",
    "request_hash",
    "tool",
]
if sorted(m.keys()) != sorted(required):
    raise SystemExit(f"unexpected manifest keys: {sorted(m.keys())}")

for forbidden_key in (
    "timestamp_utc",
    "session_id",
    "request_id",
    "prev_record_hash",
    "record_hash",
    "record_version",
    "request_bytes_b64",
    "normalized_args",
    "policy_reasons",
    "intent",
    "tool_args_redacted",
    "policy_inputs",
):
    if forbidden_key in m:
        raise SystemExit(f"forbidden key present: {forbidden_key}")

for needle in ("canonical_path", "/Users/", "\\\\", "timestamp_utc", "session_id"):
    if needle in raw:
        raise SystemExit(f"forbidden string in manifest bytes: {needle}")
PY

if [[ "$rc_002" == "0" ]]; then
  echo "PASS: T-MANIFESTDET-002 manifest field hygiene"
  pass=$((pass+1))
else
  echo "FAIL: T-MANIFESTDET-002 manifest field hygiene (exit=$rc_002)"
  fail=$((fail+1))
fi

echo
echo "--- T-MANIFESTDET-003: manifest builder ignores volatile fields and path-only normalized args ---"
rc_003=0
python3 - <<'PY' "$ROOT/scripts/policy-eval.py" || rc_003=$?
import importlib.util
import json
import sys
from pathlib import Path

mod_path = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("policy_eval", mod_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

base = {
    "cap_registry_hash": "sha256:" + ("a" * 64),
    "capability_class": "FS_MOVE",
    "request_hash": "sha256:" + ("b" * 64),
    "tool": "FS_MOVE",
    "policy_decision": "DENY",
    "policy_reasons": [
        {"code": "RC-FS-PATH-DISALLOWED", "detail": {"canonical_path": "/tmp/a"}},
        {"code": "RC-FS-OVERWRITE-DISALLOWED", "detail": "x"},
    ],
    "normalized_args": {
        "canonical_src_path": "/tmp/src-a",
        "canonical_dst_path": "/tmp/dst-a",
        "overwrite_requested": True,
    },
    "timestamp_utc": "2026-02-25T01:02:03Z",
    "session_id": "sess-a",
    "request_id": "req-a",
    "record_hash": "sha256:" + ("c" * 64),
    "record_version": "0.1",
}

variant = {
    **base,
    "timestamp_utc": "2099-01-01T00:00:00Z",
    "session_id": "sess-b",
    "request_id": "req-b",
    "record_hash": "sha256:" + ("d" * 64),
    "record_version": "9.9",
    "normalized_args": {
        "canonical_src_path": "/different/src",
        "canonical_dst_path": "/different/dst",
        "overwrite_requested": True,
    },
    "policy_reasons": [
        {"code": "RC-FS-PATH-DISALLOWED", "detail": {"canonical_path": "/different"}},
        {"code": "RC-FS-OVERWRITE-DISALLOWED", "detail": "changed"},
    ],
}

m1 = mod.build_manifest_from_record(base)
m2 = mod.build_manifest_from_record(variant)
if m1 != m2:
    raise SystemExit(
        "manifest mismatch under volatile/path-only changes\n"
        f"m1={json.dumps(m1, sort_keys=True)}\n"
        f"m2={json.dumps(m2, sort_keys=True)}"
    )

if "record_hash" in m1 or "record_version" in m1:
    raise SystemExit("manifest unexpectedly contains record_hash/record_version")
PY

if [[ "$rc_003" == "0" ]]; then
  echo "PASS: T-MANIFESTDET-003 stable-field-only manifest derivation"
  pass=$((pass+1))
else
  echo "FAIL: T-MANIFESTDET-003 stable-field-only manifest derivation (exit=$rc_003)"
  fail=$((fail+1))
fi

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
