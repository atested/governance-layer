#!/usr/bin/env python3
"""verify-qa-chain.py — independent verifier for the quality-service QA chain.

Companion to scripts/verify-chain.py. Verifies QA chain integrity end to end:
  1. Sequence numbers are strictly monotonic (sequence[i] = sequence[i-1] + 1).
  2. prev_record_hash continuity (each record links to the previous record_hash).
  3. record_hash matches a recomputation under the canonical form.
  4. event_type is in the registered set (qa-chain-events-v1.yaml).
  5. Required fields are present per event type.
  6. Ed25519 signatures verify against the QA verifying key (when available).

Exit codes
  0  PASS — all checks succeeded (or skipped with explicit flags).
  1  FAIL — one or more verification failures.
  2  Tool error — invalid arguments, missing dependencies, unreadable inputs.

Key source resolution (for signature verification):
  --qa-public-key <path>   Explicit Ed25519 public key (PEM, raw 32 bytes, or hex).
  --qa-signing-key <path>  Ed25519 private key (PEM); the public key is derived.
  ATESTED_QA_VERIFY_KEY_PATH (env)   Explicit verifying key path.
  ATESTED_QA_SIGNING_KEY_PATH (env)  Private key path; public key derived.
  GOV_QA_SIGNING_KEY_PATH (env)      Private key path; public key derived.
  Default key path:  {runtime}/.atested-qa-signing-key.pem
  --skip-signatures        Skip signature verification (e.g. for fixture chains).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from canonical_form import (
    canonical_json,
    non_action_signing_preimage,
    record_hash as compute_record_hash,
)


# ---------------------------------------------------------------------------
# QA chain event registry (source of truth: qa-chain-events-v1.yaml)
# ---------------------------------------------------------------------------
#
# Maintained in lockstep with claude-project-files/qa-chain-events-v1.yaml.
# Each entry lists required fields beyond the universal envelope
# {event_type, sequence, timestamp_utc, prev_record_hash, record_hash,
#  signature, signing_key_id}.

_UNIVERSAL_REQUIRED = (
    "event_type",
    "sequence",
    "timestamp_utc",
    "record_hash",
    "signature",
    "signing_key_id",
)

QA_EVENT_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "qa_environmental_snapshot": (
        "policy_rules_hash",
        "capability_registry_hash",
        "checks",
        "active_conditions",
        "overall",
    ),
    "qa_condition_detected": (
        "condition_id",
        "condition_type",
        "severity",
        "detail",
    ),
    "qa_decision_verification": (
        "governance_record_hash",
        "decision_type",
        "tool_name",
        "checks_performed",
        "all_clear",
    ),
    "qa_decision_verification_skipped": (
        "governance_record_hash",
        "reason",
    ),
    "qa_verification_backlog_warning": (
        "queue_depth",
        "queue_capacity",
    ),
    "qa_spc_finding": (
        "metric_id",
        "metric_name",
        "current_value",
        "window",
        "status",
    ),
    "qa_element_verification": (
        "spec_id",
        "elements_checked",
        "elements_passed",
        "elements_flagged",
        "elements_skipped",
        "findings",
        "coverage",
    ),
    "qa_behavioral_analysis": (
        "analysis_window",
        "findings",
        "anomaly_count",
    ),
    "qa_session_summary": (
        "session_start",
        "session_duration_hours",
        "decisions_verified",
        "conditions_detected",
        "environmental_snapshots",
        "final_sequence",
    ),
}

KNOWN_QA_EVENT_TYPES = frozenset(QA_EVENT_REQUIRED_FIELDS)


# ---------------------------------------------------------------------------
# Ed25519 key loading (optional — signatures may be skipped)
# ---------------------------------------------------------------------------


def _load_crypto():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
    except Exception as exc:
        return None, None, None, None, f"cryptography unavailable: {exc}"
    return InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey, None


def _key_id_from_public_raw(raw: bytes) -> str:
    import hashlib

    return "ed25519:" + hashlib.sha256(raw).hexdigest()


def _load_verifying_key(
    public_path: Optional[str], private_path: Optional[str]
) -> tuple[Optional[Any], Optional[str], Optional[str]]:
    """Return (public_key, key_id, error). Either public_path or private_path may be set."""
    InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey, err = _load_crypto()
    if err:
        return None, None, err

    chosen_public = public_path
    chosen_private = private_path
    if not chosen_public:
        chosen_public = os.environ.get("ATESTED_QA_VERIFY_KEY_PATH") or chosen_public
    if not chosen_private:
        chosen_private = (
            os.environ.get("ATESTED_QA_SIGNING_KEY_PATH")
            or os.environ.get("GOV_QA_SIGNING_KEY_PATH")
            or chosen_private
        )

    if chosen_public:
        try:
            raw = Path(chosen_public).read_bytes()
        except OSError as exc:
            return None, None, f"unable to read public key {chosen_public}: {exc}"
        pub = _parse_public_key_material(raw, serialization, Ed25519PublicKey)
        if isinstance(pub, str):
            return None, None, pub
        raw_pub = pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return pub, _key_id_from_public_raw(raw_pub), None

    if chosen_private:
        try:
            raw = Path(chosen_private).read_bytes()
        except OSError as exc:
            return None, None, f"unable to read private key {chosen_private}: {exc}"
        priv = _parse_private_key_material(raw, serialization, Ed25519PrivateKey)
        if isinstance(priv, str):
            return None, None, priv
        pub = priv.public_key()
        raw_pub = pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return pub, _key_id_from_public_raw(raw_pub), None

    return None, None, "no QA verifying or signing key configured"


def _parse_public_key_material(raw: bytes, serialization, Ed25519PublicKey):
    # Try PEM first
    try:
        pub = serialization.load_pem_public_key(raw)
        if isinstance(pub, Ed25519PublicKey):
            return pub
        return "key file is not an Ed25519 public key"
    except Exception:
        pass
    # Raw 32 bytes
    if len(raw) == 32:
        try:
            return Ed25519PublicKey.from_public_bytes(raw)
        except Exception as exc:
            return f"raw 32-byte public key invalid: {exc}"
    # Hex (64 chars, possibly newline-terminated)
    text = raw.decode("ascii", errors="ignore").strip()
    if len(text) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        try:
            return Ed25519PublicKey.from_public_bytes(bytes.fromhex(text))
        except Exception as exc:
            return f"hex public key invalid: {exc}"
    return "unsupported public key format (expected PEM, raw 32 bytes, or 64-char hex)"


def _parse_private_key_material(raw: bytes, serialization, Ed25519PrivateKey):
    try:
        priv = serialization.load_pem_private_key(raw, password=None)
        if isinstance(priv, Ed25519PrivateKey):
            return priv
        return "private key file is not Ed25519"
    except Exception:
        pass
    text = raw.decode("ascii", errors="ignore").strip()
    if len(text) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        try:
            return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(text))
        except Exception as exc:
            return f"hex private key invalid: {exc}"
    return "unsupported private key format (expected PEM or 64-char hex)"


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def _validate_required_fields(rec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in _UNIVERSAL_REQUIRED:
        if field not in rec:
            errors.append(f"missing required field '{field}'")
    event_type = rec.get("event_type")
    if not isinstance(event_type, str):
        return errors
    extra = QA_EVENT_REQUIRED_FIELDS.get(event_type, ())
    for field in extra:
        if field not in rec:
            errors.append(f"missing required field '{field}' for {event_type}")
    return errors


def _verify_record_hash(rec: dict[str, Any]) -> Optional[str]:
    stored = rec.get("record_hash")
    if not isinstance(stored, str):
        return "record_hash missing or non-string"
    recomputed = compute_record_hash(rec)
    if recomputed != stored:
        return f"record_hash mismatch: stored={stored} recomputed={recomputed}"
    return None


def _verify_signature(
    rec: dict[str, Any],
    public_key: Any,
    expected_key_id: str,
    InvalidSignature: Any,
) -> Optional[str]:
    sig = rec.get("signature")
    key_id = rec.get("signing_key_id")
    if not isinstance(sig, str) or not sig:
        return "signature missing or empty"
    if not isinstance(key_id, str) or not key_id:
        return "signing_key_id missing or empty"
    if key_id != expected_key_id:
        return f"signing_key_id mismatch: expected={expected_key_id} actual={key_id}"
    try:
        sig_bytes = _b64url_decode(sig)
    except Exception as exc:
        return f"signature not valid base64url: {exc}"
    preimage = non_action_signing_preimage(rec).encode("utf-8")
    try:
        public_key.verify(sig_bytes, preimage)
    except InvalidSignature:
        return "signature does not verify under QA public key"
    except Exception as exc:
        return f"signature verification raised: {exc}"
    return None


def verify_qa_chain(
    chain_path: Path,
    *,
    public_key: Any = None,
    expected_key_id: Optional[str] = None,
    InvalidSignature: Any = None,
    skip_signatures: bool = False,
) -> dict[str, Any]:
    """Return a summary dict; raises no exceptions for verification failures."""
    summary: dict[str, Any] = {
        "chain_path": str(chain_path),
        "total_records": 0,
        "verified_records": 0,
        "event_type_counts": {},
        "failures": [],
        "skipped_signatures": skip_signatures or public_key is None,
        "first_sequence": None,
        "last_sequence": None,
    }
    if not chain_path.exists():
        summary["failures"].append(
            {"line": 0, "code": "chain_absent", "detail": f"chain file not found: {chain_path}"}
        )
        return summary

    prev_hash: Optional[str] = None
    prev_sequence: Optional[int] = None

    with chain_path.open("r", encoding="utf-8") as fh:
        for i, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                summary["failures"].append(
                    {"line": i, "code": "invalid_json", "detail": str(exc)}
                )
                continue
            summary["total_records"] += 1

            field_errors = _validate_required_fields(rec)
            if field_errors:
                for err in field_errors:
                    summary["failures"].append(
                        {"line": i, "code": "missing_field", "detail": err}
                    )
                # Continue — we can still check what's present.

            event_type = rec.get("event_type")
            if isinstance(event_type, str):
                summary["event_type_counts"][event_type] = (
                    summary["event_type_counts"].get(event_type, 0) + 1
                )
                if event_type not in KNOWN_QA_EVENT_TYPES:
                    summary["failures"].append(
                        {
                            "line": i,
                            "code": "unknown_event_type",
                            "detail": f"event_type '{event_type}' not in qa-chain-events-v1 registry",
                        }
                    )

            sequence = rec.get("sequence")
            if not isinstance(sequence, int):
                summary["failures"].append(
                    {"line": i, "code": "missing_field", "detail": "sequence not an integer"}
                )
            else:
                if prev_sequence is not None and sequence != prev_sequence + 1:
                    summary["failures"].append(
                        {
                            "line": i,
                            "code": "sequence_gap",
                            "detail": f"sequence {sequence} not exactly prev+1 (prev={prev_sequence})",
                        }
                    )
                if summary["first_sequence"] is None:
                    summary["first_sequence"] = sequence
                summary["last_sequence"] = sequence
                prev_sequence = sequence

            link = rec.get("prev_record_hash")
            if summary["total_records"] == 1:
                if link is not None:
                    summary["failures"].append(
                        {
                            "line": i,
                            "code": "linkage_break",
                            "detail": f"first record prev_record_hash should be null, got {link!r}",
                        }
                    )
            else:
                if link != prev_hash:
                    summary["failures"].append(
                        {
                            "line": i,
                            "code": "linkage_break",
                            "detail": f"prev_record_hash mismatch: expected {prev_hash} actual {link}",
                        }
                    )

            hash_err = _verify_record_hash(rec)
            if hash_err is not None:
                summary["failures"].append(
                    {"line": i, "code": "record_hash_mismatch", "detail": hash_err}
                )

            if not skip_signatures and public_key is not None:
                sig_err = _verify_signature(rec, public_key, expected_key_id, InvalidSignature)
                if sig_err is not None:
                    summary["failures"].append(
                        {"line": i, "code": "signature_invalid", "detail": sig_err}
                    )

            prev_hash = rec.get("record_hash")
            # A record is "verified" iff no failure for THIS line.
            # Recompute against failures list seeded only this line:
            this_line_failed = any(f["line"] == i for f in summary["failures"])
            if not this_line_failed:
                summary["verified_records"] += 1

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_summary(summary: dict[str, Any]) -> None:
    chain = summary["chain_path"]
    total = summary["total_records"]
    verified = summary["verified_records"]
    failures = summary["failures"]
    if failures:
        print(f"FAIL: QA chain verification failed ({len(failures)} failures, {verified}/{total} records verified)")
        print(f"Chain: {chain}")
        for failure in failures[:50]:
            print(f"  line {failure['line']}: [{failure['code']}] {failure['detail']}")
        if len(failures) > 50:
            print(f"  ... and {len(failures) - 50} more failures")
    else:
        print(f"PASS: QA chain verified ({total} records)")
        print(f"Chain: {chain}")
    counts = summary.get("event_type_counts") or {}
    if counts:
        print("Event type counts:")
        for event_type in sorted(counts):
            print(f"  {event_type}: {counts[event_type]}")
    first_seq = summary.get("first_sequence")
    last_seq = summary.get("last_sequence")
    if first_seq is not None and last_seq is not None:
        print(f"Sequence range: {first_seq}..{last_seq}")
    if summary.get("skipped_signatures"):
        print("Signature verification: SKIPPED (no key configured or --skip-signatures)")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Verify QA chain integrity (companion to verify-chain.py)"
    )
    ap.add_argument("chain_path", help="path to qa-chain.jsonl")
    ap.add_argument("--qa-public-key", help="Ed25519 public key (PEM, raw 32 bytes, or hex)")
    ap.add_argument(
        "--qa-signing-key",
        help="Ed25519 private key (PEM or hex) — public key is derived",
    )
    ap.add_argument(
        "--skip-signatures",
        action="store_true",
        help="skip signature verification (useful for fixture chains without keys)",
    )
    ap.add_argument(
        "--summary-json",
        help="write canonical-JSON summary to this path",
    )
    args = ap.parse_args(argv)

    chain_path = Path(args.chain_path)

    public_key = None
    expected_key_id = None
    InvalidSignature = None
    if not args.skip_signatures:
        public_key, expected_key_id, key_err = _load_verifying_key(
            args.qa_public_key, args.qa_signing_key
        )
        if key_err and public_key is None:
            # No key available — fall back to skipping signatures with a notice
            print(f"NOTE: signature verification skipped — {key_err}", file=sys.stderr)
        else:
            _, _, _, _, crypto_err = _load_crypto()
            if crypto_err:
                print(f"FAIL: {crypto_err}", file=sys.stderr)
                return 2
            from cryptography.exceptions import InvalidSignature as _IS
            InvalidSignature = _IS

    summary = verify_qa_chain(
        chain_path,
        public_key=public_key,
        expected_key_id=expected_key_id,
        InvalidSignature=InvalidSignature,
        skip_signatures=args.skip_signatures or public_key is None,
    )

    _print_summary(summary)

    if args.summary_json:
        Path(args.summary_json).write_text(
            canonical_json(summary) + "\n", encoding="utf-8"
        )

    return 0 if not summary["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
