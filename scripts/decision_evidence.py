#!/usr/bin/env python3
"""Signed governance evidence for decisions, operator actions, and outcomes.

The ledger makes release/refusal ordering explicit: a terminal outcome may be
appended only after its decision record, and both records are covered by the
same append-only Ed25519-signed hash chain.  A checkpoint anchors the expected
record count and head, which makes deletion of the current tail detectable in
addition to ordinary link and record tampering.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional

try:
    from canonical_form import canonical_json, record_hash
except ImportError:  # pragma: no cover - package import path
    from scripts.canonical_form import canonical_json, record_hash


SCHEMA_ID = "SCH-GOV-EVIDENCE-001"
RECORD_TYPES = frozenset({"decision", "operator_action", "terminal_outcome"})
DECISIONS = frozenset({"ALLOW", "DENY"})
OPERATOR_ACTIONS = frozenset({"APPROVE", "REVOKE"})
TERMINAL_OUTCOMES = frozenset({"RELEASED", "REFUSED"})
_REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_:-]*$")


class DecisionEvidenceError(RuntimeError):
    """Evidence cannot be recorded without violating the governance contract."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _valid_time(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def _valid_hash(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(char in "0123456789abcdef" for char in value[7:])
    )


def _key_id(public_key: Any) -> str:
    from cryptography.hazmat.primitives import serialization

    raw = public_key.public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return "ed25519:" + hashlib.sha256(raw).hexdigest()


def _signature_preimage(record: Mapping[str, Any]) -> bytes:
    unsigned = dict(record)
    unsigned["signature"] = None
    unsigned["signing_key_id"] = None
    return canonical_json(unsigned).encode("utf-8")


def _reason_codes(value: Any, *, required: bool) -> list[str]:
    if not isinstance(value, list):
        raise DecisionEvidenceError("reason_codes must be a list")
    codes = [str(code) for code in value]
    if required and not codes:
        raise DecisionEvidenceError("DENY evidence requires at least one reason code")
    if len(codes) != len(set(codes)) or any(not _REASON_CODE.fullmatch(code) for code in codes):
        raise DecisionEvidenceError("reason_codes must be unique stable machine-parsable codes")
    return codes


def _public_key_for(record: Mapping[str, Any], public_keys: Any) -> Any:
    key_id = record.get("signing_key_id")
    if isinstance(public_keys, Mapping):
        key = public_keys.get(key_id)
    else:
        key = public_keys
    if key is None or _key_id(key) != key_id:
        raise DecisionEvidenceError("signing_key_id has no matching verification key")
    return key


def _verify_record(record: Any, public_keys: Any) -> None:
    if not isinstance(record, Mapping):
        raise DecisionEvidenceError("record is not an object")
    required = (
        "schema_id", "record_id", "record_type", "recorded_at", "operation_id",
        "payload", "prev_record_hash", "record_hash", "signature", "signing_key_id",
    )
    missing = [field for field in required if field not in record]
    if missing:
        raise DecisionEvidenceError(f"record missing required field: {missing[0]}")
    if record["schema_id"] != SCHEMA_ID:
        raise DecisionEvidenceError("unknown evidence schema")
    if not isinstance(record["record_id"], str) or not record["record_id"]:
        raise DecisionEvidenceError("record_id must be non-empty")
    if record["record_type"] not in RECORD_TYPES:
        raise DecisionEvidenceError("record_type is not governed evidence")
    if not _valid_time(record["recorded_at"]):
        raise DecisionEvidenceError("recorded_at must be a valid UTC time")
    if not isinstance(record["operation_id"], str) or not record["operation_id"]:
        raise DecisionEvidenceError("operation_id must be non-empty")
    if not isinstance(record["payload"], Mapping):
        raise DecisionEvidenceError("payload must be an object")
    if record["prev_record_hash"] is not None and not _valid_hash(record["prev_record_hash"]):
        raise DecisionEvidenceError("prev_record_hash is invalid")
    if not _valid_hash(record["record_hash"]) or record_hash(dict(record)) != record["record_hash"]:
        raise DecisionEvidenceError("record_hash mismatch")
    if not isinstance(record["signature"], str) or not record["signature"]:
        raise DecisionEvidenceError("record is unsigned")
    key = _public_key_for(record, public_keys)
    try:
        padded = record["signature"] + "=" * ((4 - len(record["signature"]) % 4) % 4)
        key.verify(base64.urlsafe_b64decode(padded), _signature_preimage(record))
    except Exception as exc:
        raise DecisionEvidenceError("Ed25519 signature verification failed") from exc


def _verify_semantics(records: list[Mapping[str, Any]]) -> None:
    decisions: dict[str, Mapping[str, Any]] = {}
    operator_actions: dict[str, Mapping[str, Any]] = {}
    terminal_decisions: set[str] = set()

    for record in records:
        record_type = record["record_type"]
        payload = record["payload"]
        operation_id = record["operation_id"]
        if record_type == "operator_action":
            operator_id = payload.get("authenticated_operator_id")
            action = payload.get("action")
            if not isinstance(operator_id, str) or not operator_id:
                raise DecisionEvidenceError("operator action lacks authenticated operator identity")
            if action not in OPERATOR_ACTIONS:
                raise DecisionEvidenceError("operator action must be APPROVE or REVOKE")
            if not _valid_time(payload.get("decision_time")):
                raise DecisionEvidenceError("operator action lacks a valid decision time")
            operator_actions[record["record_id"]] = record
            continue

        if record_type == "decision":
            decision = payload.get("decision")
            if decision not in DECISIONS:
                raise DecisionEvidenceError("decision must be ALLOW or DENY")
            if not isinstance(payload.get("policy_context"), Mapping) or not payload["policy_context"]:
                raise DecisionEvidenceError("decision lacks policy context")
            _reason_codes(payload.get("reason_codes"), required=decision == "DENY")
            basis = payload.get("decision_basis")
            action_id = payload.get("operator_action_record_id")
            if basis == "operator_approval":
                action = operator_actions.get(action_id)
                if action is None or action["operation_id"] != operation_id or action["payload"].get("action") != "APPROVE":
                    raise DecisionEvidenceError("approval-derived decision lacks an earlier matching approval")
            elif action_id is not None:
                raise DecisionEvidenceError("policy decision cannot cite an operator action")
            decisions[record["record_id"]] = record
            continue

        decision_id = payload.get("decision_record_id")
        decision_record = decisions.get(decision_id)
        if decision_record is None:
            raise DecisionEvidenceError("terminal outcome lacks exactly one earlier decision record")
        if decision_id in terminal_decisions:
            raise DecisionEvidenceError("decision record already has a terminal outcome")
        if payload.get("decision_record_hash") != decision_record["record_hash"]:
            raise DecisionEvidenceError("terminal outcome decision hash does not correlate")
        if decision_record["operation_id"] != operation_id:
            raise DecisionEvidenceError("terminal outcome operation does not correlate")
        decision = decision_record["payload"]["decision"]
        expected_outcome = "RELEASED" if decision == "ALLOW" else "REFUSED"
        if payload.get("outcome") != expected_outcome:
            raise DecisionEvidenceError("terminal outcome conflicts with its decision")
        decision_codes = decision_record["payload"]["reason_codes"]
        terminal_codes = _reason_codes(payload.get("reason_codes"), required=decision == "DENY")
        if terminal_codes != decision_codes:
            raise DecisionEvidenceError("denial reason codes do not correlate to the same decision")
        terminal_decisions.add(decision_id)


def verify_signed_chain(
    chain_path: Path,
    public_keys: Any,
    *,
    checkpoint: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Return an integrity result identifying the first affected boundary."""
    path = Path(chain_path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    except OSError as exc:
        return {"valid": False, "first_affected_boundary": 1, "reason": f"chain unreadable: {exc}"}

    records: list[Mapping[str, Any]] = []
    previous: Optional[str] = None
    seen_ids: set[str] = set()
    for index, line in enumerate(lines, start=1):
        if not line:
            return {"valid": False, "first_affected_boundary": index, "reason": "blank record"}
        try:
            record = json.loads(line)
            _verify_record(record, public_keys)
            if record["record_id"] in seen_ids:
                raise DecisionEvidenceError("duplicate record_id")
            if record["prev_record_hash"] != previous:
                raise DecisionEvidenceError("predecessor linkage mismatch")
        except (json.JSONDecodeError, DecisionEvidenceError) as exc:
            return {"valid": False, "first_affected_boundary": index, "reason": str(exc)}
        records.append(record)
        seen_ids.add(record["record_id"])
        previous = record["record_hash"]

    try:
        _verify_semantics(records)
    except DecisionEvidenceError as exc:
        # Semantics are evaluated in order, so the first record whose prefix
        # cannot be valid is the first affected boundary.
        for index in range(1, len(records) + 1):
            try:
                _verify_semantics(records[:index])
            except DecisionEvidenceError:
                return {"valid": False, "first_affected_boundary": index, "reason": str(exc)}

    if checkpoint is not None:
        expected_count = checkpoint.get("record_count")
        expected_head = checkpoint.get("head_record_hash")
        if expected_count != len(records):
            boundary = min(len(records), int(expected_count or 0)) + 1
            return {"valid": False, "first_affected_boundary": boundary, "reason": "checkpoint record count mismatch"}
        if expected_head != previous:
            return {"valid": False, "first_affected_boundary": max(1, len(records)), "reason": "checkpoint head mismatch"}

    return {
        "valid": True,
        "record_count": len(records),
        "head_record_hash": previous,
        "first_affected_boundary": None,
        "reason": None,
    }


class SignedGovernanceLedger:
    """Cross-process append-only writer for signed governance evidence."""

    def __init__(self, chain_path: Path, signing_key: Any, *, lock_timeout_seconds: float = 5.0):
        if signing_key is None:
            raise DecisionEvidenceError("an Ed25519 signing key is required")
        self.chain_path = Path(chain_path)
        self.signing_key = signing_key
        self.public_key = signing_key.public_key()
        self.signing_key_id = _key_id(self.public_key)
        self.lock_timeout_seconds = lock_timeout_seconds

    @contextmanager
    def _lock(self) -> Iterator[None]:
        lock_path = Path(str(self.chain_path) + ".lock.d")
        deadline = time.monotonic() + self.lock_timeout_seconds
        while True:
            try:
                lock_path.mkdir()
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise DecisionEvidenceError("timed out acquiring evidence-chain lock")
                time.sleep(0.02)
        try:
            yield
        finally:
            try:
                lock_path.rmdir()
            except OSError:
                pass

    def _read_verified(self) -> list[dict[str, Any]]:
        result = verify_signed_chain(self.chain_path, self.public_key)
        if not result["valid"]:
            raise DecisionEvidenceError(
                f"chain integrity failed at boundary {result['first_affected_boundary']}: {result['reason']}"
            )
        if not self.chain_path.exists():
            return []
        return [json.loads(line) for line in self.chain_path.read_text(encoding="utf-8").splitlines()]

    def _append(self, record_type: str, operation_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        operation = str(operation_id or "").strip()
        if not operation:
            raise DecisionEvidenceError("operation_id is required")
        with self._lock():
            records = self._read_verified()
            record: dict[str, Any] = {
                "schema_id": SCHEMA_ID,
                "record_id": str(uuid.uuid4()),
                "record_type": record_type,
                "recorded_at": _now(),
                "operation_id": operation,
                "payload": dict(payload),
                "prev_record_hash": records[-1]["record_hash"] if records else None,
                "record_hash": None,
                "signature": None,
                "signing_key_id": None,
            }
            record["record_hash"] = record_hash(record)
            record["signature"] = base64.urlsafe_b64encode(
                self.signing_key.sign(_signature_preimage(record))
            ).decode("ascii").rstrip("=")
            record["signing_key_id"] = self.signing_key_id
            _verify_record(record, self.public_key)
            _verify_semantics([*records, record])
            self.chain_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(self.chain_path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, (canonical_json(record) + "\n").encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)
            return record

    def record_operator_action(
        self,
        operation_id: str,
        *,
        authenticated_operator_id: str,
        action: str,
        decision_time: Optional[str] = None,
    ) -> dict[str, Any]:
        return self._append("operator_action", operation_id, {
            "authenticated_operator_id": str(authenticated_operator_id or "").strip(),
            "action": str(action or "").upper(),
            "decision_time": decision_time or _now(),
        })

    def record_decision(
        self,
        operation_id: str,
        *,
        decision: str,
        policy_context: Mapping[str, Any],
        reason_codes: Optional[list[str]] = None,
        operator_action_record_id: Optional[str] = None,
    ) -> dict[str, Any]:
        normalized_decision = str(decision or "").upper()
        payload: dict[str, Any] = {
            "decision": normalized_decision,
            "decision_basis": "operator_approval" if operator_action_record_id else "policy",
            "policy_context": dict(policy_context),
            "reason_codes": list(reason_codes or []),
        }
        if operator_action_record_id:
            payload["operator_action_record_id"] = operator_action_record_id
        return self._append("decision", operation_id, payload)

    def record_terminal_outcome(
        self,
        decision_record: Mapping[str, Any],
    ) -> dict[str, Any]:
        decision = decision_record.get("payload", {}).get("decision")
        return self._append("terminal_outcome", str(decision_record.get("operation_id", "")), {
            "outcome": "RELEASED" if decision == "ALLOW" else "REFUSED",
            "decision_record_id": decision_record.get("record_id"),
            "decision_record_hash": decision_record.get("record_hash"),
            "reason_codes": list(decision_record.get("payload", {}).get("reason_codes", [])),
        })

    def checkpoint(self) -> dict[str, Any]:
        result = verify_signed_chain(self.chain_path, self.public_key)
        if not result["valid"]:
            raise DecisionEvidenceError(
                f"chain integrity failed at boundary {result['first_affected_boundary']}: {result['reason']}"
            )
        return {
            "schema_id": SCHEMA_ID,
            "record_count": result["record_count"],
            "head_record_hash": result["head_record_hash"],
        }

