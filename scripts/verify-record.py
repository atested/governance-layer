#!/usr/bin/env python3
import base64
import json
import sys
import hashlib
from pathlib import Path

CAP_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "capabilities" / "capability-registry.json"

def compute_cap_registry_hash() -> str:
    data = CAP_REGISTRY_PATH.read_bytes()
    return "sha256:" + hashlib.sha256(data).hexdigest()

def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def main():
    if len(sys.argv) != 2:
        print("Usage: verify-record.py <decision-record.json>", file=sys.stderr)
        sys.exit(2)

    p = sys.argv[1]
    with open(p, "r", encoding="utf-8") as f:
        rec = json.load(f)

    # Verify cap_registry_hash
    expected_cap_hash = compute_cap_registry_hash()
    got_cap_hash = rec.get("cap_registry_hash")
    if not got_cap_hash:
        print("FAIL: missing cap_registry_hash")
        sys.exit(2)
    if got_cap_hash != expected_cap_hash:
        print(f"FAIL: cap_registry_hash mismatch (got={got_cap_hash}, expected={expected_cap_hash})")
        sys.exit(2)

    # Verify request_hash against embedded request bytes (if present — older records omit it).
    got_request_hash = rec.get("request_hash")
    got_b64 = rec.get("request_bytes_b64")
    if got_request_hash is not None or got_b64 is not None:
        if not got_request_hash or not got_b64:
            print("FAIL: request_hash/request_bytes_b64 present but incomplete")
            sys.exit(2)
        if not got_request_hash.startswith("sha256:"):
            print("FAIL: request_hash has unexpected format")
            sys.exit(2)
        try:
            raw = base64.b64decode(got_b64)
        except Exception as e:
            print(f"FAIL: request_bytes_b64 not valid base64: {e}")
            sys.exit(2)
        recomputed = "sha256:" + hashlib.sha256(raw).hexdigest()
        if recomputed != got_request_hash:
            print(f"FAIL: request_hash mismatch (got={got_request_hash}, recomputed={recomputed})")
            sys.exit(2)

    expected = rec.get("record_hash")
    if not isinstance(expected, str) or not expected.startswith("sha256:"):
        print("FAIL: record_hash missing or invalid")
        sys.exit(1)

    unsigned = dict(rec)
    unsigned["record_hash"] = None
    unsigned["signature"] = None

    payload = canonical_json(unsigned)
    actual = "sha256:" + sha256_hex(payload)

    if actual != expected:
        print("FAIL: record_hash mismatch")
        print(" expected:", expected)
        print(" actual:  ", actual)
        sys.exit(1)

    print("PASS: record_hash verified")
    sys.exit(0)

if __name__ == "__main__":
    main()
