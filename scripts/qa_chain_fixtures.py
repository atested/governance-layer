#!/usr/bin/env python3
"""Synthetic QA chain fixtures for proxy quality-gate tests."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except Exception:  # pragma: no cover - tests require cryptography
    Ed25519PrivateKey = None

from canonical_form import (
    ED25519_TEST_PRIVATE_SEED_HEX,
    canonical_json,
    non_action_signing_preimage,
    record_hash,
)


TEST_QA_SIGNING_KEY_ID = "ed25519-test-vector"


def _test_signing_key():
    if Ed25519PrivateKey is None:
        return None
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(ED25519_TEST_PRIVATE_SEED_HEX))


def _sign_record(record: dict) -> dict:
    record["record_hash"] = record_hash(record)
    signing_key = _test_signing_key()
    if signing_key is None:
        record["signature"] = ""
        record["signing_key_id"] = TEST_QA_SIGNING_KEY_ID
        return record
    sig = signing_key.sign(non_action_signing_preimage(record).encode("utf-8"))
    import base64
    record["signature"] = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    record["signing_key_id"] = TEST_QA_SIGNING_KEY_ID
    return record


def qa_environmental_snapshot(
    *,
    sequence: int,
    policy_rules_hash: str,
    capability_registry_hash: str,
    prev_record_hash: Optional[str] = None,
    overall: str = "healthy",
    active_conditions: Optional[list] = None,
) -> dict:
    record = {
        "event_type": "qa_environmental_snapshot",
        "sequence": sequence,
        "timestamp_utc": "2026-05-23T14:30:00Z",
        "policy_rules_hash": policy_rules_hash,
        "capability_registry_hash": capability_registry_hash,
        "checks": {
            "ENV-001": {"status": "pass"},
            "ENV-003": {"status": "pass"},
            "ENV-004": {"status": "pass"},
            "ENV-005": {"status": "pass"},
            "ENV-009": {"status": "pass"},
            "ENV-010": {"status": "pass"},
        },
        "active_conditions": active_conditions or [],
        "overall": overall,
        "prev_record_hash": prev_record_hash,
        "record_hash": None,
        "signature": None,
        "signing_key_id": None,
    }
    return _sign_record(record)


def write_qa_chain(path: Path, records: list[dict]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(canonical_json(record) + "\n" for record in records),
        encoding="utf-8",
    )
    return path


def write_fixture(
    path: Path,
    fixture: str,
    *,
    policy_rules_hash: str,
    capability_registry_hash: str,
) -> Path:
    if fixture == "absent":
        path = Path(path)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return path
    if fixture == "empty":
        return write_qa_chain(path, [])

    policy_hash = policy_rules_hash
    cap_hash = capability_registry_hash
    active_conditions = []
    overall = "healthy"
    if fixture == "condition":
        active_conditions = ["CR-CRIT-001"]
    elif fixture == "hash_mismatch":
        policy_hash = "sha256:" + "0" * 64
    elif fixture not in {"healthy", "stale"}:
        raise ValueError(f"unknown fixture: {fixture}")

    record = qa_environmental_snapshot(
        sequence=1,
        policy_rules_hash=policy_hash,
        capability_registry_hash=cap_hash,
        overall=overall,
        active_conditions=active_conditions,
    )
    return write_qa_chain(path, [record])


def write_large_fixture(
    path: Path,
    *,
    count: int,
    policy_rules_hash: str,
    capability_registry_hash: str,
) -> Path:
    records = []
    prev = None
    for sequence in range(1, count + 1):
        record = qa_environmental_snapshot(
            sequence=sequence,
            policy_rules_hash=policy_rules_hash,
            capability_registry_hash=capability_registry_hash,
            prev_record_hash=prev,
        )
        prev = record["record_hash"]
        records.append(record)
    return write_qa_chain(path, records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create synthetic QA chain fixtures")
    parser.add_argument("path")
    parser.add_argument("fixture", choices=["healthy", "stale", "condition", "hash_mismatch", "empty", "absent"])
    parser.add_argument("--policy-rules-hash", required=True)
    parser.add_argument("--capability-registry-hash", required=True)
    args = parser.parse_args()
    write_fixture(
        Path(args.path),
        args.fixture,
        policy_rules_hash=args.policy_rules_hash,
        capability_registry_hash=args.capability_registry_hash,
    )


if __name__ == "__main__":
    main()
