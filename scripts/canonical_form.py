#!/usr/bin/env python3
"""A tested canonical JSON and signing-preimage reference implementation.

This module is intentionally standalone.  It defines the Python ground truth
that the Rust quality service must match byte-for-byte.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


CANONICAL_JSON_KWARGS = {
    "sort_keys": True,
    "separators": (",", ":"),
    "ensure_ascii": False,
    "allow_nan": False,
}

SIGNING_EXCLUDE_TOP_LEVEL = frozenset(
    [
        "timestamp_utc",
        "session_id",
        "request_id",
        "process_id",
        "record_hash",
        "signature",
        "signing_key_id",
        "request_bytes_b64",
        "evidence_refs",
        "untrusted_inputs",
    ]
)

SIGNING_EXCLUDE_TOP_LEVEL_LEGACY = frozenset(
    [
        "timestamp_utc",
        "session_id",
        "request_id",
        "process_id",
        "prev_record_hash",
        "record_hash",
        "signature",
        "signing_key_id",
        "request_bytes_b64",
        "evidence_refs",
        "untrusted_inputs",
    ]
)

ED25519_TEST_PRIVATE_SEED_HEX = (
    "000102030405060708090a0b0c0d0e0f"
    "101112131415161718191a1b1c1d1e1f"
)
ED25519_TEST_MESSAGE = (
    '{"event_type":"qa_environmental_snapshot","overall":"healthy","sequence":1}'
)


def canonical_json(obj: Any) -> str:
    """Return Atested canonical JSON as a Unicode string."""
    return json.dumps(obj, **CANONICAL_JSON_KWARGS)


def canonicalize(obj: Any) -> bytes:
    """Return Atested canonical JSON encoded as UTF-8 bytes."""
    return canonical_json(obj).encode("utf-8")


def sha256_hex_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_prefixed_bytes(data: bytes) -> str:
    return "sha256:" + sha256_hex_bytes(data)


def sha256_prefixed(obj: Any) -> str:
    return sha256_prefixed_bytes(canonicalize(obj))


def with_nulled_fields(obj: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    copy_obj = dict(obj)
    for field in fields:
        copy_obj[field] = None
    return copy_obj


def record_hash_preimage(record: dict[str, Any]) -> str:
    """Canonical preimage for v2 mediated decisions and non-action events."""
    body = dict(record)
    body["record_hash"] = None
    if "signature" in body:
        body["signature"] = None
    if "signing_key_id" in body:
        body["signing_key_id"] = None
    return canonical_json(body)


def record_hash(record: dict[str, Any]) -> str:
    return sha256_prefixed_bytes(record_hash_preimage(record).encode("utf-8"))


def metadata_hash_preimage(metadata: dict[str, Any]) -> str:
    body = dict(metadata)
    body["metadata_hash"] = None
    return canonical_json(body)


def metadata_hash(metadata: dict[str, Any]) -> str:
    return sha256_prefixed_bytes(metadata_hash_preimage(metadata).encode("utf-8"))


def registry_hash_preimage(registry: dict[str, Any]) -> str:
    body = dict(registry)
    body["registry_hash"] = None
    return canonical_json(body)


def registry_hash(registry: dict[str, Any]) -> str:
    return sha256_prefixed_bytes(registry_hash_preimage(registry).encode("utf-8"))


def approval_store_hash(approvals: list[dict[str, Any]] | None = None) -> str:
    normalized = {
        "approval_store_version": "0.1",
        "active_approvals": sorted(
            list(approvals or []),
            key=lambda row: canonical_json(row),
        ),
    }
    return sha256_prefixed(normalized)


def _sanitize_expected_outputs_for_signing(expected_outputs: Any) -> list[Any]:
    sanitized: list[Any] = []
    for item in expected_outputs or []:
        if not isinstance(item, dict):
            sanitized.append(item)
            continue
        cleaned = dict(item)
        ref = cleaned.get("ref")
        if isinstance(ref, str) and ref.endswith(":path") and "value" in cleaned:
            cleaned["value"] = "<path-redacted>"
        sanitized.append(cleaned)
    return sanitized


def signing_preimage_payload(
    record: dict[str, Any],
    exclude_set: frozenset[str] | None = None,
) -> str:
    """Match scripts/verify-record.py signing_preimage_payload."""
    if exclude_set is None:
        exclude_set = SIGNING_EXCLUDE_TOP_LEVEL
    unsigned = copy.deepcopy(record)
    for key in exclude_set:
        unsigned.pop(key, None)

    if isinstance(unsigned.get("policy_reasons"), list):
        unsigned["policy_reasons"] = [
            {"code": reason.get("code")} if isinstance(reason, dict) else reason
            for reason in unsigned["policy_reasons"]
        ]

    if isinstance(unsigned.get("tool_args_redacted"), dict):
        unsigned["tool_args_redacted"].pop("path", None)
        unsigned["tool_args_redacted"].pop("canonical_path", None)

    if isinstance(unsigned.get("policy_inputs"), dict):
        unsigned["policy_inputs"].pop("canonical_path", None)
        unsigned["policy_inputs"].pop("allow_base_dirs", None)

    if isinstance(unsigned.get("normalized_args"), dict):
        for key in ("canonical_path", "canonical_src_path", "canonical_dst_path"):
            unsigned["normalized_args"].pop(key, None)

    if isinstance(unsigned.get("intent"), dict):
        unsigned["intent"]["expected_outputs"] = _sanitize_expected_outputs_for_signing(
            unsigned["intent"].get("expected_outputs", [])
        )

    return canonical_json(unsigned)


def non_action_signing_preimage(event: dict[str, Any]) -> str:
    body = dict(event)
    body["record_hash"] = None
    body["signature"] = None
    body["signing_key_id"] = None
    return canonical_json(body)


def _b64url_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _ed25519_signature_vector() -> dict[str, Any]:
    try:
        import cryptography
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except Exception as exc:  # pragma: no cover - depends on local environment
        return {"available": False, "error": str(exc)}

    seed = bytes.fromhex(ED25519_TEST_PRIVATE_SEED_HEX)
    private_key = Ed25519PrivateKey.from_private_bytes(seed)
    public_key = private_key.public_key()
    public_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    signature = private_key.sign(ED25519_TEST_MESSAGE.encode("utf-8"))
    return {
        "available": True,
        "python_cryptography_version": cryptography.__version__,
        "algorithm": "Ed25519 pure, no prehash",
        "private_key_seed_hex": ED25519_TEST_PRIVATE_SEED_HEX,
        "private_key_pkcs8_pem": private_pem,
        "public_key_raw_hex": public_raw.hex(),
        "public_key_fingerprint": "ed25519:" + hashlib.sha256(public_raw).hexdigest(),
        "public_key_spki_pem": public_pem,
        "message": ED25519_TEST_MESSAGE,
        "signature_hex": signature.hex(),
        "signature_base64url_nopad": _b64url_nopad(signature),
    }


def _vector(
    vector_id: str,
    notes: str,
    input_obj: Any,
    *,
    signing_mode: str | None = None,
    hash_mode: str | None = None,
) -> dict[str, Any]:
    canonical = canonical_json(input_obj)
    vector: dict[str, Any] = {
        "id": vector_id,
        "input": input_obj,
        "canonical_json": canonical,
        "sha256": sha256_prefixed_bytes(canonical.encode("utf-8")),
        "signing_preimage": None,
        "notes": notes,
    }
    if signing_mode == "v2_mediated_decision":
        vector["signing_preimage"] = signing_preimage_payload(input_obj)
        vector["signing_preimage_sha256"] = sha256_prefixed_bytes(
            vector["signing_preimage"].encode("utf-8")
        )
    elif signing_mode == "non_action_event":
        vector["signing_preimage"] = non_action_signing_preimage(input_obj)
        vector["signing_preimage_sha256"] = sha256_prefixed_bytes(
            vector["signing_preimage"].encode("utf-8")
        )

    if hash_mode == "record":
        preimage = record_hash_preimage(input_obj)
        vector["record_hash_preimage"] = preimage
        vector["record_hash_sha256"] = sha256_prefixed_bytes(preimage.encode("utf-8"))
    elif hash_mode == "metadata":
        preimage = metadata_hash_preimage(input_obj)
        vector["metadata_hash_preimage"] = preimage
        vector["metadata_hash_sha256"] = sha256_prefixed_bytes(preimage.encode("utf-8"))
    elif hash_mode == "registry":
        preimage = registry_hash_preimage(input_obj)
        vector["registry_hash_preimage"] = preimage
        vector["registry_hash_sha256"] = sha256_prefixed_bytes(preimage.encode("utf-8"))
    return vector


def build_conformance_vectors() -> dict[str, Any]:
    mediated = {
        "record_version": "2.0",
        "record_type": "mediated_decision",
        "timestamp_utc": "2026-05-23T14:30:00Z",
        "session_id": "sess-001",
        "request_id": "req-001",
        "process_id": 4242,
        "original_tool": "bash",
        "policy_decision": "DENY",
        "matched_rule": "deny_shell_write",
        "classification": {"category": "shell", "risk_tier": 3, "targets": ["tmp/out.txt"]},
        "policy_reasons": [
            {"code": "V2_DENY_SHELL_WRITE", "detail": {"reason": "shell write denied"}},
            {"code": "V2_AUDIT", "detail": {"reason": "extra detail omitted from signing"}},
        ],
        "tool_args_redacted": {"path": "/tmp/out.txt", "canonical_path": "/private/tmp/out.txt", "command": "echo hi"},
        "policy_inputs": {"canonical_path": "/private/tmp/out.txt", "allow_base_dirs": ["/tmp"], "tier": "deny"},
        "normalized_args": {
            "canonical_path": "/private/tmp/out.txt",
            "canonical_src_path": "/private/tmp/a",
            "canonical_dst_path": "/private/tmp/b",
            "visible": "kept",
        },
        "intent": {
            "expected_outputs": [
                {"ref": "output:path", "value": "/tmp/out.txt", "kind": "path"},
                {"ref": "output:text", "value": "kept", "kind": "text"},
            ]
        },
        "request_bytes_b64": "ZXhhbXBsZQ==",
        "evidence_refs": ["sha256:" + "a" * 64],
        "untrusted_inputs": [{"source": "tool_args"}],
        "prev_record_hash": "sha256:" + "0" * 64,
        "record_hash": "sha256:" + "1" * 64,
        "signature": "sig",
        "signing_key_id": "ed25519:key",
    }
    non_action = {
        "event_model_version": "0.1",
        "event_type": "telemetry_submitted",
        "event_id": "evt-001",
        "timestamp_utc": "2026-05-23T14:30:01Z",
        "destination": "https://license.atested.com/api/telemetry",
        "payload_hash": "sha256:" + "2" * 64,
        "payload_size": 512,
        "prev_record_hash": "sha256:" + "1" * 64,
        "record_hash": "sha256:" + "3" * 64,
        "signature": "sig",
        "signing_key_id": "ed25519:key",
    }
    vectors = [
        _vector("V001", "simple ASCII object and sorted keys", {"z": "last", "a": "first"}),
        _vector("V002", "multi-byte UTF-8 CJK, emoji, and raw non-ASCII output", {"emoji": "🧪", "cjk": "漢字", "accent": "café"}),
        _vector("V003", "combining character sequence without Unicode normalization", {"nfd_like": "e\u0301", "nfc_like": "é"}),
        _vector("V004", "positive, negative, and zero integers", {"positive": 42, "negative": -17, "zero": 0}),
        _vector("V005", "large integer beyond int64 but valid JSON integer", {"big": 9223372036854775808, "small": -9223372036854775809}),
        _vector("V006", "float zero and negative zero", {"zero": 0.0, "negative_zero": -0.0}),
        _vector("V007", "ordinary floats and Python shortest-roundtrip rendering", {"one_point_one": 1.1, "sum": 0.1 + 0.2}),
        _vector("V008", "small floats and scientific notation boundary", {"small": 1e-06, "smaller": 1e-07, "tiny": 5e-324}),
        _vector("V009", "large floats and scientific notation", {"large_plain": 1e16, "large_sci": 1.23e45}),
        _vector("V010", "integer-valued float retains decimal form", {"one_float": 1.0, "trailing_zero_source": 1.2300}),
        _vector("V011", "null, booleans, and strings", {"none": None, "true": True, "false": False, "text": "yes"}),
        _vector("V012", "empty object and array", {"empty_object": {}, "empty_array": []}),
        _vector("V013", "nested objects and arrays", {"outer": {"b": [3, 2, 1], "a": {"inner": True}}}),
        _vector("V014", "mixed-type array", {"array": [None, True, False, 1, -2.5, "x", {"k": "v"}, []]}),
        _vector("V015", "deeply nested structure", {"a": {"b": {"c": {"d": {"e": ["leaf"]}}}}}),
        _vector("V016", "non-sorted insertion order and mixed-case keys", {"b": 1, "A": 2, "a": 3, "B": 4}),
        _vector("V017", "Unicode keys sort by Unicode code point", {"é": 1, "e\u0301": 2, "中": 3, "a": 4}),
        _vector("V018", "escaped JSON control characters", {"quote": "\"", "backslash": "\\", "newline": "\n", "tab": "\t"}),
        _vector("V019", "v2 mediated decision hash and signing preimage", mediated, signing_mode="v2_mediated_decision", hash_mode="record"),
        _vector("V020", "non-action governance event hash and signing preimage", non_action, signing_mode="non_action_event", hash_mode="record"),
        _vector(
            "V021",
            "integrity metadata hash with metadata_hash nulled",
            {"schema_version": 1, "metadata_hash": "sha256:" + "4" * 64, "policy_rules_hash": "sha256:" + "5" * 64},
            hash_mode="metadata",
        ),
        _vector(
            "V022",
            "machine registry hash with registry_hash nulled",
            {"registry_version": 1, "registry_hash": "sha256:" + "6" * 64, "machines": [{"id": "m2"}, {"id": "m1"}]},
            hash_mode="registry",
        ),
        _vector(
            "V023",
            "approval store snapshot with approval ordering inputs",
            {
                "approval_store_version": "0.1",
                "active_approvals": sorted(
                    [
                        {"artifact_identity": "sha256:bbb", "policy_version": "baseline-v1"},
                        {"artifact_identity": "sha256:aaa", "policy_version": "baseline-v1"},
                    ],
                    key=lambda row: canonical_json(row),
                ),
            },
        ),
        _vector(
            "V024",
            "QA environmental snapshot shape from quality service spec",
            {
                "event_type": "qa_environmental_snapshot",
                "sequence": 48217,
                "timestamp_utc": "2026-05-23T14:30:00Z",
                "policy_rules_hash": "sha256:" + "a" * 64,
                "capability_registry_hash": "sha256:" + "b" * 64,
                "checks": {
                    "ENV-001": {"status": "pass"},
                    "ENV-007": {"status": "pass", "disk_available_mb": 2048},
                },
                "active_conditions": [],
                "overall": "healthy",
            },
        ),
        _vector(
            "V025",
            "QA condition detected shape",
            {
                "event_type": "qa_condition_detected",
                "sequence": 48218,
                "timestamp_utc": "2026-05-23T14:30:00.123Z",
                "condition_id": "CR-CRIT-001",
                "condition_type": "stale_rules",
                "severity": "critical",
                "detail": "policy_rules_hash mismatch",
                "governance_record_ref": "sha256:" + "c" * 64,
            },
        ),
        _vector(
            "V026",
            "QA decision verification shape",
            {
                "event_type": "qa_decision_verification",
                "sequence": 48219,
                "timestamp_utc": "2026-05-23T14:30:01Z",
                "governance_record_hash": "sha256:" + "d" * 64,
                "decision_type": "ALLOW",
                "tool_name": "bash",
                "checks_performed": {
                    "structural_integrity": "pass",
                    "classification_consistency": "pass",
                    "approval_provenance": "pass",
                },
                "all_clear": True,
            },
        ),
        _vector(
            "V027",
            "QA SPC finding shape with bounded ratio values",
            {
                "event_type": "qa_spc_finding",
                "sequence": 48222,
                "timestamp_utc": "2026-05-23T14:30:00Z",
                "metric_id": "SPC-001",
                "metric_name": "ALLOW rate",
                "current_value": 0.97,
                "ucl": 0.82,
                "lcl": 0.38,
                "window": "1h",
                "status": "above_ucl",
            },
        ),
        _vector(
            "V028",
            "QA element verification shape",
            {
                "event_type": "qa_element_verification",
                "sequence": 48223,
                "timestamp_utc": "2026-05-23T14:30:00Z",
                "spec_id": "chain-integrity-v1",
                "elements_checked": 12,
                "elements_passed": 10,
                "elements_flagged": 1,
                "elements_skipped": 1,
                "findings": [{"element_id": "REQ-CHN-005", "severity": "high"}],
                "coverage": {"active_verified": 10, "contradictory": 2},
            },
        ),
        _vector(
            "V029",
            "QA behavioral analysis nested finding shape",
            {
                "event_type": "qa_behavioral_analysis",
                "sequence": 48300,
                "timestamp_utc": "2026-05-23T15:00:00Z",
                "analysis_window": "1h",
                "findings": [
                    {
                        "type": "classification_inconsistency",
                        "tool_name": "file_write",
                        "evidence_records": ["sha256:" + "e" * 64, "sha256:" + "f" * 64],
                        "severity": "medium",
                    }
                ],
                "anomaly_count": 1,
            },
        ),
        _vector(
            "V030",
            "QA session summary shape",
            {
                "event_type": "qa_session_summary",
                "sequence": 50000,
                "timestamp_utc": "2026-05-23T18:00:00Z",
                "session_start": "2026-05-23T08:00:00Z",
                "session_duration_hours": 10,
                "decisions_verified": 1247,
                "conditions_detected": 3,
                "conditions_by_type": {"classification_anomaly": 1, "stale_rules": 2},
                "final_sequence": 50000,
            },
        ),
    ]
    return {
        "schema_version": "canonical-form-v1-vectors",
        "generated_by": "scripts/canonical_form.py",
        "canonical_json_kwargs": {
            "sort_keys": True,
            "separators": [",", ":"],
            "ensure_ascii": False,
            "allow_nan": False,
        },
        "vectors": vectors,
        "invalid_vectors": [
            {"id": "INV001", "input": {"nan": "NaN"}, "notes": "NaN is represented as a string here; numeric NaN must be rejected by canonical_json."},
            {"id": "INV002", "input": {"infinity": "Infinity"}, "notes": "Infinity is represented as a string here; numeric Infinity must be rejected by canonical_json."},
        ],
        "ed25519_signature_vector": _ed25519_signature_vector(),
    }


def _assert_no_non_finite(obj: Any) -> None:
    if isinstance(obj, float) and not math.isfinite(obj):
        raise ValueError("non-finite float must be rejected")
    if isinstance(obj, dict):
        for value in obj.values():
            _assert_no_non_finite(value)
    elif isinstance(obj, list):
        for value in obj:
            _assert_no_non_finite(value)


def validate_vector_set(path: Path) -> tuple[bool, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for vector in data.get("vectors", []):
        vector_id = vector.get("id", "<missing>")
        try:
            _assert_no_non_finite(vector["input"])
            canonical = canonical_json(vector["input"])
        except Exception as exc:
            errors.append(f"{vector_id}: canonicalization failed: {exc}")
            continue
        if canonical != vector.get("canonical_json"):
            errors.append(f"{vector_id}: canonical_json mismatch")
        expected_hash = sha256_prefixed_bytes(canonical.encode("utf-8"))
        if expected_hash != vector.get("sha256"):
            errors.append(f"{vector_id}: sha256 mismatch")
        signing_preimage = vector.get("signing_preimage")
        if signing_preimage is not None:
            mode = None
            if "v2 mediated" in str(vector.get("notes", "")):
                mode = "v2_mediated_decision"
            elif "non-action" in str(vector.get("notes", "")):
                mode = "non_action_event"
            if mode == "v2_mediated_decision":
                actual = signing_preimage_payload(vector["input"])
            elif mode == "non_action_event":
                actual = non_action_signing_preimage(vector["input"])
            else:
                actual = signing_preimage
            if actual != signing_preimage:
                errors.append(f"{vector_id}: signing_preimage mismatch")
            expected = sha256_prefixed_bytes(signing_preimage.encode("utf-8"))
            if expected != vector.get("signing_preimage_sha256"):
                errors.append(f"{vector_id}: signing_preimage_sha256 mismatch")
        if "record_hash_preimage" in vector:
            actual = record_hash_preimage(vector["input"])
            if actual != vector["record_hash_preimage"]:
                errors.append(f"{vector_id}: record_hash_preimage mismatch")
            expected = sha256_prefixed_bytes(actual.encode("utf-8"))
            if expected != vector.get("record_hash_sha256"):
                errors.append(f"{vector_id}: record_hash_sha256 mismatch")
        if "metadata_hash_preimage" in vector:
            actual = metadata_hash_preimage(vector["input"])
            if actual != vector["metadata_hash_preimage"]:
                errors.append(f"{vector_id}: metadata_hash_preimage mismatch")
        if "registry_hash_preimage" in vector:
            actual = registry_hash_preimage(vector["input"])
            if actual != vector["registry_hash_preimage"]:
                errors.append(f"{vector_id}: registry_hash_preimage mismatch")

    try:
        canonical_json({"bad": float("nan")})
        errors.append("numeric NaN was not rejected")
    except ValueError:
        pass
    try:
        canonical_json({"bad": float("inf")})
        errors.append("numeric Infinity was not rejected")
    except ValueError:
        pass

    sig_vector = data.get("ed25519_signature_vector", {})
    if sig_vector.get("available"):
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            private_key = Ed25519PrivateKey.from_private_bytes(
                bytes.fromhex(sig_vector["private_key_seed_hex"])
            )
            signature = private_key.sign(sig_vector["message"].encode("utf-8"))
            if signature.hex() != sig_vector.get("signature_hex"):
                errors.append("ed25519 signature_hex mismatch")
            public_key = serialization.load_pem_public_key(
                sig_vector["public_key_spki_pem"].encode("ascii")
            )
            public_key.verify(signature, sig_vector["message"].encode("utf-8"))
        except Exception as exc:
            errors.append(f"ed25519 signature vector validation failed: {exc}")
    return not errors, errors


def write_vectors(path: Path) -> None:
    data = build_conformance_vectors()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atested canonical form reference")
    parser.add_argument("--write-vectors", type=Path)
    parser.add_argument("--validate-vectors", type=Path)
    args = parser.parse_args(argv)

    if args.write_vectors:
        write_vectors(args.write_vectors)
    if args.validate_vectors:
        ok, errors = validate_vector_set(args.validate_vectors)
        if not ok:
            for error in errors:
                print(error)
            return 1
        vector_count = len(json.loads(args.validate_vectors.read_text(encoding="utf-8")).get("vectors", []))
        print(f"PASS: {vector_count} canonical vectors validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
