#!/usr/bin/env python3
import sys, json, hashlib

def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def verify_record_hash(rec: dict) -> bool:
    expected = rec.get("record_hash")
    if not isinstance(expected, str) or not expected.startswith("sha256:"):
        return False
    unsigned = dict(rec)
    unsigned["record_hash"] = None
    unsigned["signature"] = None
    payload = canonical_json(unsigned)
    actual = "sha256:" + sha256_hex(payload)
    return actual == expected

def main():
    if len(sys.argv) != 2:
        print("Usage: verify-chain.py <decision-chain.jsonl>", file=sys.stderr)
        sys.exit(2)

    path = sys.argv[1]
    prev_hash = None
    i = 0

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            i += 1
            try:
                rec = json.loads(line)
            except Exception:
                print(f"FAIL: line {i}: invalid JSON")
                sys.exit(1)

            if not verify_record_hash(rec):
                print(f"FAIL: line {i}: record_hash verification failed")
                sys.exit(1)

            link = rec.get("prev_record_hash")
            if i == 1:
                # first record may have null/None prev
                pass
            else:
                if link != prev_hash:
                    print(f"FAIL: line {i}: prev_record_hash mismatch")
                    print(f" expected: {prev_hash}")
                    print(f" actual:   {link}")
                    sys.exit(1)

            prev_hash = rec.get("record_hash")

    print(f"PASS: chain verified ({i} records)")
    sys.exit(0)

if __name__ == "__main__":
    main()
