#!/usr/bin/env python3
"""
replay-record.py — Deterministic replay verifier for governance decision records.

Replays the original request embedded in a decision record and asserts that the
replay output matches the original on all deterministic invariants:
  1. policy_decision  (ALLOW / DENY)
  2. reason_codes     (ordered list of policy_reasons[*].code)
  3. tool             (registered tool name)
  4. cap_registry_hash (internal on-disk registry hash at replay time)
  5. normalized_args  (strict deep-equal)

Non-deterministic fields (timestamp_utc, session_id, request_id, record_hash,
prev_record_hash) are intentionally excluded from comparison.

Requires records produced at Phase 2B.3 or later (request_bytes_b64 + request_hash
must be present). Pre-2B.3 records are rejected with a clear error.

Usage:
    replay-record.py <decision-record.json>

Exit codes:
    0 — all invariants match
    1 — invariant mismatch (diff printed to stdout)
    2 — fatal error (missing fields, hash mismatch, subprocess failure)
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
POLICY_EVAL = SCRIPTS / "policy-eval.py"

NON_DETERMINISTIC = frozenset([
    "timestamp_utc",
    "session_id",
    "request_id",
    "record_hash",
    "prev_record_hash",
    "signature",
    "signing_key_id",
    # request_bytes_b64 and request_hash are identical by construction (same bytes),
    # so they would always match — but we verify them separately via sha256 check.
])


def sha256_hex(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def extract_reason_codes(record: dict) -> list:
    return [r["code"] for r in record.get("policy_reasons", [])]


def compare_invariants(orig: dict, replay: dict) -> list:
    """Return list of mismatch dicts for deterministic invariants."""
    mismatches = []
    checks = [
        ("policy_decision",  orig.get("policy_decision"),   replay.get("policy_decision")),
        ("tool",             orig.get("tool"),               replay.get("tool")),
        ("cap_registry_hash", orig.get("cap_registry_hash"), replay.get("cap_registry_hash")),
        ("normalized_args",  orig.get("normalized_args"),   replay.get("normalized_args")),
        ("reason_codes",     extract_reason_codes(orig),    extract_reason_codes(replay)),
    ]
    for field, old_val, new_val in checks:
        if old_val != new_val:
            mismatches.append({"field": field, "original": old_val, "replay": new_val})
    return mismatches


def main():
    if len(sys.argv) != 2:
        print("Usage: replay-record.py <decision-record.json>", file=sys.stderr)
        sys.exit(2)

    record_path = sys.argv[1]
    try:
        with open(record_path, "r", encoding="utf-8") as f:
            orig = json.load(f)
    except Exception as e:
        print(f"FAIL: cannot load record '{record_path}': {e}", file=sys.stderr)
        sys.exit(2)

    # Require embedded request bytes (Phase 2B.3+ records only).
    b64 = orig.get("request_bytes_b64")
    stored_hash = orig.get("request_hash")
    if not b64 or not stored_hash:
        print(
            "FAIL: record missing request_bytes_b64 or request_hash.\n"
            "  Only records produced at Phase 2B.3 or later are replayable.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Decode and verify request bytes hash before any evaluation.
    try:
        raw = base64.b64decode(b64)
    except Exception as e:
        print(f"FAIL: request_bytes_b64 is not valid base64: {e}", file=sys.stderr)
        sys.exit(2)

    recomputed_hash = sha256_hex(raw)
    if recomputed_hash != stored_hash:
        print(
            f"FAIL: request_hash mismatch (record tampered or corrupted)\n"
            f"  stored:     {stored_hash}\n"
            f"  recomputed: {recomputed_hash}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Write raw bytes to an isolated temp file; no path injection possible.
    with tempfile.TemporaryDirectory(prefix="gov_replay_") as tdir:
        tmp_intent = Path(tdir) / "replay_intent.json"
        tmp_intent.write_bytes(raw)

        # Invoke policy-eval with no external registry arg (internal path only).
        result = subprocess.run(
            [sys.executable, str(POLICY_EVAL), str(tmp_intent)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(
                f"FAIL: policy-eval exited {result.returncode} during replay.\n"
                f"  stderr: {result.stderr.strip()}",
                file=sys.stderr,
            )
            sys.exit(2)

        replay_out = result.stdout.strip()
        if not replay_out:
            print(
                f"FAIL: policy-eval produced no output during replay.\n"
                f"  stderr: {result.stderr.strip()}",
                file=sys.stderr,
            )
            sys.exit(2)

        try:
            replay = json.loads(replay_out)
        except Exception as e:
            print(f"FAIL: policy-eval replay output is not valid JSON: {e}", file=sys.stderr)
            sys.exit(2)

    # Compare deterministic invariants.
    mismatches = compare_invariants(orig, replay)
    if not mismatches:
        decision = orig.get("policy_decision", "?")
        tool = orig.get("tool", "?")
        codes = extract_reason_codes(orig)
        print(
            f"PASS: replay matches original "
            f"(decision={decision}, tool={tool}, reason_codes={codes})"
        )
        sys.exit(0)
    else:
        print(f"FAIL: replay mismatch on {len(mismatches)} invariant(s):")
        for m in mismatches:
            print(f"  field:    {m['field']}")
            print(f"  original: {m['original']}")
            print(f"  replay:   {m['replay']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
